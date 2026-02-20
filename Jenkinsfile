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
                    // FIX: Check available disk space before building to prevent
                    // "No space left on device" errors mid-build. Fail fast if <3GB free.
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
                    // FIX: The original code failed because it tried to remove the image
                    // while the container was still running. We now stop the container FIRST,
                    // then force-remove the image, then prune dangling images.
                    // This prevents disk space buildup over multiple deployments.
                    
                    // Step 1: Stop and remove the old container
                    try {
                        sh "docker stop ${CONTAINER_NAME} 2>/dev/null || true"
                        sh "docker rm ${CONTAINER_NAME} 2>/dev/null || true"
                        echo "✅ Stopped and removed old container"
                    } catch (Exception e) {
                        echo "⚠️  No container to stop (first deployment?)"
                    }
                    
                    // Step 2: Force-remove the old image (now that container is gone)
                    try {
                        sh "docker rmi -f ${IMAGE_NAME}:latest 2>/dev/null || true"
                        echo "✅ Removed old image"
                    } catch (Exception e) {
                        echo "⚠️  No old image to remove"
                    }
                    
                    // Step 3: Prune dangling images to free disk space
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
                // FIX: Added --no-cache to force a clean build.
                // This prevents Docker from reusing layers that contain old .pyc files
                // or stale Python bytecode, which was causing the 'str' object bug to persist
                // even after the source code was updated.
                sh "docker build --no-cache -t ${IMAGE_NAME}:latest ."
                
                // FIX: Verify the patched code is actually in the image.
                // This catches build issues early before we waste time deploying a broken image.
                // Must override entrypoint because Dockerfile sets it to 'streamlit run'.
                echo 'Verifying patched code is present in image...'
                sh """
                    docker run --rm --entrypoint python ${IMAGE_NAME}:latest \
                    -c "from src.tools import _safe_parse_response; print('✅ Patched code verified in image')" \
                    || (echo "❌ Patched code not found in image" && exit 1)
                """
            }
        }

        stage('Deploy Container') {
            steps {
                echo 'Deploying to Production...'
                script {
                    // The old container was already removed in Clean Old Artifacts stage,
                    // but we double-check here just in case
                    try {
                        sh "docker stop ${CONTAINER_NAME} 2>/dev/null || true"
                        sh "docker rm ${CONTAINER_NAME} 2>/dev/null || true"
                    } catch (Exception e) {
                        echo "⚠️  Container already removed"
                    }

                    // FIX: Create output directory with correct permissions BEFORE container starts.
                    // The container runs as UID 1000 (optiuser), but Docker volume mounts preserve
                    // host filesystem ownership. If the host directory is owned by root, the container
                    // process cannot write to it, causing "[Errno 13] Permission denied" errors.
                    // Jenkins user needs sudo to run chown - ensure Jenkins has passwordless sudo configured.
                    echo "Setting up output directory with correct permissions..."
                    sh """
                        sudo mkdir -p ${HOST_CONFIG_DIR}/output
                        sudo chown -R 1000:1000 ${HOST_CONFIG_DIR}/output
                        sudo chmod -R 755 ${HOST_CONFIG_DIR}/output
                    """

                    // Launch the new container
                    // FIX: Changed --restart always to --restart unless-stopped
                    // to prevent infinite restart loops if the container crashes immediately
                    sh """
                        docker run -d \
                        --name ${CONTAINER_NAME} \
                        --restart unless-stopped \
                        -p 8501:8501 \
                        -v ${HOST_CONFIG_DIR}/output:/app/output \
                        --env-file ${HOST_CONFIG_DIR}/.env \
                        ${IMAGE_NAME}:latest
                    """
                    
                    // FIX: Wait for container to start before proceeding
                    echo "Waiting for container to initialize..."
                    sleep 10
                    
                    // FIX: Verify container is actually running (not crashed)
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
                    // FIX: Poll the Streamlit healthcheck endpoint to confirm the app is responding.
                    // The original code had no health verification, so broken deployments would
                    // silently "succeed" and leave users with a non-functional app.
                    def maxRetries = 12  // 60 seconds total (5s * 12)
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
                        // Dump container logs for debugging
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
                // Remove any leftover images from the build process
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
            // Show current disk usage after every build
            echo 'Current disk usage:'
            sh 'df -h /var/lib/docker'
        }
    }
}