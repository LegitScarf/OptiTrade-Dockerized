pipeline {
    agent any

    environment {
        // Points to our "Home Base" on the server
        DEPLOY_DIR = "/home/ubuntu/optitrade_live"
    }

    stages {
        stage('Deploy Code') {
            steps {
                echo 'Copying files to production directory...'
                // Copy all files from Jenkins workspace to the live folder
                // We exclude .git and venv to prevent overwriting setup
                sh "cp -r ./* ${DEPLOY_DIR}/"
            }
        }

        stage('Update Dependencies') {
            steps {
                echo 'Installing Python requirements...'
                // Run pip install inside the virtual environment
                sh "${DEPLOY_DIR}/venv/bin/pip install -r ${DEPLOY_DIR}/requirements.txt"
            }
        }

        stage('Restart Application') {
            steps {
                echo 'Restarting OptiTrade Service...'
                // Restart the systemd service to pick up code changes
                sh "sudo systemctl restart optitrade"
            }
        }
    }
}