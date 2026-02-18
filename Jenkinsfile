pipeline {
    agent any

    environment {
        IMAGE_NAME = "optitrade"
        CONTAINER_NAME = "optitrade_app"
        HOST_CONFIG_DIR = "/opt/optitrade"
    }

    stages {
        stage('Validate Environment') {
            steps {
                echo 'Validating configuration files...'
                script {
                    // FIX: Verify .env exists on the host before deploying.
                    // Without this, the container starts but crashes on first API call.
                    def envFile = "${HOST_CONFIG_DIR}/.env"
                    if (!fileExists(envFile)) {
                        error("❌ .env file missing at ${envFile} — cannot deploy without API credentials")
                    }
                    
                    // FIX: Verify required keys are present in .env
                    def required = ["ANGEL_API_KEY", "ANGEL_CLIENT_ID", "ANGEL_MPIN", "ANGEL_TOTP_SECRET"]
                    def content = readFile(envFile)
                    required.each { key ->
                        if (!content.contains("${key}=")) {
                            error("❌ Required key '${key}' missing from .env")
                        }
                    }
                    
                    // FIX: Verify src/ directory exists in the build context
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
                    // FIX: Force-remove the old image so Docker can't use stale layers.
                    // Without this, 'docker build' might reuse cached layers from the
                    // broken version even if the source files changed.
                    try {
                        sh "docker rmi ${IMAGE_NAME}:latest"
                        echo "✅ Removed old image"
                    } catch (Exception e) {
                        echo "⚠️  No old image to remove (first build?)"
                    }
                }
            }
        }

        stage('Build Image') {
            steps {
                echo 'Building Docker Image from scratch...'
                // FIX: Added --no-cache to force a clean build.
                // This prevents Docker from reusing layers that contain old .pyc files.
                sh "docker build --no-cache -t ${IMAGE_NAME}:latest ."
                
                // FIX: Verify the patched code is actually in the image
                sh """
                    docker run --rm ${IMAGE_NAME}:latest \
                    python -c "from src.tools import _safe_parse_response; print('✅ Patched code verified')"
                """
            }
        }

        stage('Deploy Container') {
            steps {
                echo 'Deploying to Production...'
                script {
                    try {
                        sh "docker stop ${CONTAINER_NAME}"
                        sh "docker rm ${CONTAINER_NAME}"
                        echo "✅ Stopped old container"
                    } catch (Exception e) {
                        echo "⚠️  No existing container (first deployment?)"
                    }

                    sh """
                        docker run -d \
                        --name ${CONTAINER_NAME} \
                        --restart always \
                        -p 8501:8501 \
                        -v ${HOST_CONFIG_DIR}/output:/app/output \
                        --env-file ${HOST_CONFIG_DIR}/.env \
                        ${IMAGE_NAME}:latest
                    """
                    
                    // FIX: Wait for container to become healthy before marking deploy as success
                    echo "Waiting for container to start..."
                    sleep 10
                    sh "docker ps | grep ${CONTAINER_NAME} || exit 1"
                    echo "✅ Container deployed successfully"
                }
            }
        }

        stage('Cleanup') {
            steps {
                echo 'Removing dangling images...'
                sh "docker image prune -f"
            }
        }
        
        stage('Verify Deployment') {
            steps {
                echo 'Verifying application health...'
                script {
                    // FIX: Poll the healthcheck endpoint to confirm Streamlit is responding
                    def maxRetries = 12  // 60 seconds total (5s * 12)
                    def healthy = false
                    
                    for (int i = 0; i < maxRetries; i++) {
                        try {
                            sh "curl --fail --silent http://localhost:8501/_stcore/health"
                            healthy = true
                            break
                        } catch (Exception e) {
                            echo "⏳ Waiting for app to become healthy... (${i+1}/${maxRetries})"
                            sleep 5
                        }
                    }
                    
                    if (!healthy) {
                        error("❌ Application failed to become healthy after deployment")
                    }
                    
                    echo "✅ Application is healthy and accepting requests"
                }
            }
        }
    }
    
    post {
        success {
            echo '✅ Deployment completed successfully'
        }
        failure {
            echo '❌ Deployment failed — check logs with: docker logs ${CONTAINER_NAME}'
        }
    }
}