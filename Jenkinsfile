// Jenkinsfile
pipeline {

    agent any

    options {
		// 丢弃旧的构建，只保留最近的2个
        buildDiscarder(logRotator(numToKeepStr: '2'))
    }

 	parameters {
		string(name: 'HARBOR_REGISTRY', defaultValue: 'registry.bsoft.com.cn', description: 'Harbor url')
		//string(name: 'HARBOR_PROJECT', defaultValue: 'zarra', description: 'The name of the project in Harbor.')
		string(name: 'IMAGE_NAME', defaultValue: 'smart-assistant', description: 'The Docker image name in Harbor.')
		string(name: 'NAMESPACE', defaultValue: 'payment', description: 'k8s namespace.')

    }

    // 2. 定义整个流水线中可用的环境变量
    environment {
		// 使用 Jenkins 内置的 BUILD_NUMBER 变量作为镜像标签，确保唯一性
        IMAGE_TAG = "${env.BRANCH_NAME}-${env.BUILD_NUMBER}"
        PATH = "/usr/bin:${env.PATH}"
    }

    // 3. 定义流水线的各个阶段
    stages {
		// 阶段一：检出代码
        stage('Checkout Code') {
			steps {
				echo '--> Checking out source code from Git...'
                // 'scm' 是一个特殊变量，代表 Jenkins Job 中配置的源代码管理
                checkout scm
            }
        }

        // 阶段二：构建镜像
        stage('Build Image') {
			steps {

				script {
					// 构造完整的镜像名称，例如：harbor.yourcompany.com/your-project-name/fastapi-demo-app:1.0.12
                    //def fullImageName = "${params.HARBOR_REGISTRY}/${params.HARBOR_PROJECT}/${params.IMAGE_NAME}:${env.IMAGE_TAG}"
                    def fullImageName = "${params.HARBOR_REGISTRY}/${params.IMAGE_NAME}:${env.IMAGE_TAG}"

                    echo "--> Building image: ${fullImageName}"

                    // 调用我们的构建脚本，并把完整的镜像名称作为参数传进去
                    sh "docker build -f ./Dockerfile -t ${fullImageName} ."
                }
            }
        }

        // 阶段三：推送镜像到 Harbor
         stage('Push Image to Harbor') {
			steps {
				// 使用 Jenkins 的凭据管理器来安全地处理 Harbor 的用户名和密码
                // 'harbor-credentials-id' 是您需要在 Jenkins 中创建的凭据 ID

					script {
					def fullImageName = "${params.HARBOR_REGISTRY}/${params.IMAGE_NAME}:${env.IMAGE_TAG}"

                        //echo "--> Logging in to Harbor: ${env.HARBOR_REGISTRY}"
						//
                        //sh "buildah login -u '${env.HARBOR_USER}' -p '${env.HARBOR_PASS}' ${env.HARBOR_REGISTRY}"

                        echo "--> Pushing image: ${fullImageName}"
                        sh "docker push ${fullImageName}"
                    }

            }
        }


		stage('Deploy to K8S') {
			steps {
				script{
					echo "--> Deploy K8s"
					sh 'env'
					sh "sed -i 's/<REGISTRY>/${params.HARBOR_REGISTRY}/' deployment.yaml"
					sh "sed -i 's/<IMAGE_NAME>/${params.IMAGE_NAME}/' deployment.yaml"
					sh "sed -i 's/<IMAGE_TAG>/${env.IMAGE_TAG}/' deployment.yaml"
					sh "sed -i 's/<BRANCH>/${env.BRANCH_NAME}/'  deployment.yaml"
					sh "sed -i 's/<NAMESPACE>/${params.NAMESPACE}/'  deployment.yaml"

					sh "kubectl apply -f deployment.yaml --namespace=${params.NAMESPACE} --record"
                }

			}
        }
   	}

    // 4. 定义流水线完成后执行的动作 (无论成功或失败)
    post {
		always {
			script {
				// 清理工作空间和本地镜像，保持 Agent 干净
                def fullImageName = "${params.HARBOR_REGISTRY}/${params.IMAGE_NAME}:${env.IMAGE_TAG}"

                echo '--> Cleaning up...'

                //echo "--> Logging out from Harbor: ${params.HARBOR_REGISTRY}"
                //sh "buildah logout ${params.HARBOR_REGISTRY}"

                echo "--> Removing local image: ${fullImageName}"
                // 使用 -f 强制删除，即使有多个标签
                sh "docker rmi -f ${fullImageName} || true"
            }
        }
    }
}