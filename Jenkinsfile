pipeline {
    agent any

    environment {
        // Naming our Docker artifacts
        IMAGE_NAME = "optitrade"
        CONTAINER_NAME = "optitrade_app"
        
        // The "Source of Truth" directories we just created on the server
        HOST_CONFIG_DIR = "/opt/optitrade"
    }

    stages {
        stage('Build Image') {
            steps {
                echo 'Building Docker Image...'
                // Builds the image using the Dockerfile in the current directory
                // Tags it as 'latest' so we always run the newest code
                sh "docker build -t ${IMAGE_NAME}:latest ."
            }
        }

        stage('Deploy Container') {
            steps {
                echo 'Deploying to Production...'
                script {
                    // 1. Cleanup: Stop and remove the old container if it exists
                    // We use try/catch so the build doesn't fail if this is the very first run
                    try {
                        sh "docker stop ${CONTAINER_NAME}"
                        sh "docker rm ${CONTAINER_NAME}"
                    } catch (Exception e) {
                        echo "No existing container found (First deployment?)"
                    }

                    // 2. Launch: Run the new container
                    // -d: Detached mode (runs in background)
                    // --restart always: Auto-restarts if the server reboots or app crashes
                    // -p 8501:8501: Maps port 8501 inside container to 8501 on server
                    // -v: Mounts the output folder so reports persist on the server
                    // --env-file: Injects the API keys from the secure server file
                    sh """
                        docker run -d \
                        --name ${CONTAINER_NAME} \
                        --restart always \
                        -p 8501:8501 \
                        -v ${HOST_CONFIG_DIR}/output:/app/output \
                        --env-file ${HOST_CONFIG_DIR}/.env \
                        ${IMAGE_NAME}:latest
                    """
                }
            }
        }

        stage('Cleanup') {
            steps {
                echo 'Removing unused images...'
                // Removes "dangling" images (old versions) to save disk space
                sh "docker image prune -f"
            }
        }
    }
}