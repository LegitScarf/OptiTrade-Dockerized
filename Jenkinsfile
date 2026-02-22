pipeline {
    agent any

    environment {
        IMAGE_NAME = "optitrade"
        CONTAINER_NAME = "optitrade_app"
        HOST_CONFIG_DIR = "/opt/optitrade"
    }

    stages {
        stage('Pre-Flight Checks') {
            steps {
                echo 'Checking system resources...'
                script {
                    try {
                        def diskCheck = sh(
                            script: "df -BG /var/lib/docker | awk 'NR==2 {print \$4}' | sed 's/G//'",
                            returnStdout: true
                        ).trim().toInteger()

                        if (diskCheck < 3) {
                            error("❌ Insufficient disk space: ${diskCheck}GB free. Need at least 3GB. Run: docker system prune -a --volumes -f")
                        }

                        echo "✅ Disk space OK: ${diskCheck}GB available"
                    } catch (Exception e) {
                        echo "⚠️  Could not check disk space, proceeding anyway: ${e.message}"
                    }
                }
            }
        }

        stage('Validate Environment') {
            steps {
                echo 'Validating configuration files...'
                script {
                    def envFile = "${HOST_CONFIG_DIR}/.env"
                    if (!fileExists(envFile)) {
                        error("❌ .env file missing at ${envFile} — cannot deploy without API credentials")
                    }

                    def required = ["ANGEL_API_KEY", "ANGEL_CLIENT_ID", "ANGEL_MPIN", "ANGEL_TOTP_SECRET"]
                    def content = readFile(envFile)
                    required.each { key ->
                        if (!content.contains("${key}=")) {
                            error("❌ Required key '${key}' missing from .env")
                        }
                    }

                    if (!fileExists("src/tools.py")) {
                        error("❌ src/tools.py not found — check repository structure")
                    }

                    echo "✅ All validation checks passed"
                }
            }
        }

        stage('Clean Old Artifacts') {
            steps {
                echo 'Removing old Docker artifacts...'
                script {
                    try {
                        sh "docker stop ${CONTAINER_NAME} 2>/dev/null || true"
                        sh "docker rm ${CONTAINER_NAME} 2>/dev/null || true"
                        echo "✅ Stopped and removed old container"
                    } catch (Exception e) {
                        echo "⚠️  No container to stop (first deployment?)"
                    }

                    try {
                        sh "docker rmi -f ${IMAGE_NAME}:latest 2>/dev/null || true"
                        echo "✅ Removed old image"
                    } catch (Exception e) {
                        echo "⚠️  No old image to remove"
                    }

                    try {
                        sh "docker image prune -f"
                        echo "✅ Pruned dangling images"
                    } catch (Exception e) {
                        echo "⚠️  Prune failed: ${e.message}"
                    }
                }
            }
        }

        stage('Build Image') {
            steps {
                echo 'Building Docker Image from scratch...'
                sh "docker build --no-cache -t ${IMAGE_NAME}:latest ."

                echo 'Verifying patched code is present in image...'
                sh """
                    docker run --rm --entrypoint python ${IMAGE_NAME}:latest \
                    -c "from src.tools import _safe_parse_response; print('✅ Patched code verified in image')" \
                    || (echo "❌ Patched code not found in image" && exit 1)
                """

                // FIX: Verify SMART_API_LOG_PATH is correctly set in the image
                // so permission errors on the logs directory are caught at build
                // time rather than silently at runtime.
                echo 'Verifying SMART_API_LOG_PATH is set in image...'
                sh """
                    docker run --rm --entrypoint python ${IMAGE_NAME}:latest \
                    -c "import os; v=os.environ.get('SMART_API_LOG_PATH',''); assert v=='/tmp', f'SMART_API_LOG_PATH not set correctly: {v}'; print('✅ SMART_API_LOG_PATH=/tmp verified')" \
                    || (echo "❌ SMART_API_LOG_PATH not set correctly in image" && exit 1)
                """
            }
        }

        stage('Deploy Container') {
            steps {
                echo 'Deploying to Production...'
                script {
                    try {
                        sh "docker stop ${CONTAINER_NAME} 2>/dev/null || true"
                        sh "docker rm ${CONTAINER_NAME} 2>/dev/null || true"
                    } catch (Exception e) {
                        echo "⚠️  Container already removed"
                    }

                    echo "Setting up output directory..."
                    sh """
                        mkdir -p ${HOST_CONFIG_DIR}/output
                    """

                    sh """
                        docker run -d \
                        --name ${CONTAINER_NAME} \
                        --restart unless-stopped \
                        --user \$(id -u):\$(id -g) \
                        -e HOME=/tmp \
                        -e PYTHONUSERBASE=/tmp/.local \
                        -e SMART_API_LOG_PATH=/tmp \
                        -p 8501:8501 \
                        -v ${HOST_CONFIG_DIR}/output:/app/output \
                        --env-file ${HOST_CONFIG_DIR}/.env \
                        ${IMAGE_NAME}:latest
                    """

                    echo "Waiting for container to initialize..."
                    sleep 10

                    def containerRunning = sh(
                        script: "docker ps --filter name=${CONTAINER_NAME} --filter status=running --quiet",
                        returnStdout: true
                    ).trim()

                    if (!containerRunning) {
                        error("❌ Container failed to start. Check logs: docker logs ${CONTAINER_NAME}")
                    }

                    echo "✅ Container deployed and running"
                }
            }
        }

        stage('Verify Deployment') {
            steps {
                echo 'Verifying application health...'
                script {
                    def maxRetries = 12
                    def healthy = false

                    for (int i = 0; i < maxRetries; i++) {
                        try {
                            sh "curl --fail --silent http://localhost:8501/_stcore/health"
                            healthy = true
                            echo "✅ Application is healthy"
                            break
                        } catch (Exception e) {
                            if (i < maxRetries - 1) {
                                echo "⏳ Waiting for app to become healthy... (${i+1}/${maxRetries})"
                                sleep 5
                            }
                        }
                    }

                    if (!healthy) {
                        echo "Container logs:"
                        sh "docker logs --tail 50 ${CONTAINER_NAME}"
                        error("❌ Application failed to become healthy after ${maxRetries * 5} seconds")
                    }
                }
            }
        }

        stage('Cleanup') {
            steps {
                echo 'Final cleanup: removing dangling images...'
                sh "docker image prune -f"
            }
        }
    }

    post {
        success {
            echo '✅✅✅ Deployment completed successfully ✅✅✅'
            echo "Access the application at: http://localhost:8501"
        }
        failure {
            echo '❌❌❌ Deployment failed ❌❌❌'
            echo "Check container logs: docker logs ${CONTAINER_NAME}"
            echo "Check disk space: df -h"
            echo "Manual cleanup: docker system prune -a --volumes -f"
        }
        always {
            echo 'Current disk usage:'
            sh 'df -h /var/lib/docker'
        }
    }
}