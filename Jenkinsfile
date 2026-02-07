pipeline {
    agent any
    environment {
        IMAGE_NAME = "optitrade"
        CONTAINER_NAME = "optitrade_app"
    }
    stages {
        stage('Build Image') {
            steps {
                echo 'Building Docker Image...'
                // Build the image tagged as 'latest'
                sh "docker build -t ${IMAGE_NAME}:latest ."
            }
        }
        stage('Deploy Container') {
            steps {
                echo 'Deploying new version...'
                script {
                    // 1. Stop and remove the old container (if it exists)
                    try {
                        sh "docker stop ${CONTAINER_NAME}"
                        sh "docker rm ${CONTAINER_NAME}"
                    } catch (Exception e) {
                        echo "No existing container to remove."
                    }
                    
                    // 2. Run the new container
                    // Note: Ensure your Jenkins server has the .env file with API keys at /home/ubuntu/optitrade_live/.env
                    sh """
                        docker run -d \
                        --name ${CONTAINER_NAME} \
                        --restart always \
                        -p 8501:8501 \
                        -v /home/ubuntu/optitrade_live/output:/app/output \
                        --env-file /home/ubuntu/optitrade_live/.env \
                        ${IMAGE_NAME}:latest
                    """
                }
            }
        }
        stage('Cleanup') {
            steps {
                echo 'Pruning unused images...'
                sh "docker image prune -f"
            }
        }
    }
}