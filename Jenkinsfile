pipeline {
    agent any

    options {
        disableConcurrentBuilds()
    }

    environment {
        BRANCH_NAME = "${env.CHANGE_BRANCH ?: env.BRANCH_NAME}"
        PARENT_PATH = "/var/jenkins_home/workspace"
        REPO_URL = "https://github.com/calacademy-research/cas-web-asset-server.git"
    }

    stages {
        stage('Queued Build') {
            steps {
                script {
                    // Retry mechanism to wait and reattempt if lock is unavailable
                    retry(120) { // Adjust the retry count if necessary
                        lock(resource: 'pipeline_build_queue') {
                            echo 'Acquired lock for pipeline_build_queue. Proceeding with build stages...'

                            // Start the remaining build stages after acquiring the lock

                            // Checkout stage
                            stage('Checkout') {
                                steps {
                                    script {
                                        if (env.CHANGE_ID) {
                                            checkout([
                                                $class: 'GitSCM',
                                                branches: [[name: "FETCH_HEAD"]],
                                                extensions: [],
                                                userRemoteConfigs: [[
                                                    url: env.REPO_URL,
                                                    refspec: "+refs/pull/${env.CHANGE_ID}/head"
                                                ]]
                                            ])
                                            sh "git checkout FETCH_HEAD"
                                        } else {
                                            checkout scm
                                            sh "git fetch --all"
                                            sh "git reset --hard origin/${BRANCH_NAME}"
                                        }
                                    }
                                }
                            }

                            // Find and Save Directory stage
                            stage('Find and Save Directory') {
                                steps {
                                    script {
                                        def dirName = "${WORKSPACE}"
                                        if (dirName) {
                                            env.FOUND_DIR = dirName
                                        } else {
                                            error "Directory containing 'allbranch_${BRANCH_NAME}' and not containing '@tmp' not found"
                                        }
                                    }
                                }
                            }

                            // Copy non-tracked files stage
                            stage('Copy non-tracked files') {
                                steps {
                                    script {
                                        sh "cp ${PARENT_PATH}/web-asset-server-ci/settings.py ${env.FOUND_DIR}/settings.py"
                                        sh "cp ${PARENT_PATH}/web-asset-server-ci/server_jenkins.sh ${env.FOUND_DIR}/server_jenkins.sh"
                                        sh "cp ${PARENT_PATH}/web-asset-server-ci/server_jenkins_config.sh ${env.FOUND_DIR}/server_jenkins_config.sh"
                                        sh "cp ${PARENT_PATH}/web-asset-server-ci/docker-compose.yml ${env.FOUND_DIR}/docker-compose.yml"
                                        sh "cp ${PARENT_PATH}/web-asset-server-ci/images_ddl.sql ${env.FOUND_DIR}/images_ddl.sql"
                                        sh "cp ${PARENT_PATH}/web-asset-server-ci/nginx_test.conf ${env.FOUND_DIR}/nginx.conf"
                                    }
                                }
                            }

                            // Run Script stage
                            stage('Run Script') {
                                steps {
                                    script {
                                        sh "cd ${env.FOUND_DIR} && ./server_jenkins.sh"
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
