.PHONY: install lint test poc e2e poc-down eks-up eks-test eks-down site

install:
	pip install -e '.[test]'

lint:
	oslab lint 'policies/*.yaml'

test: lint
	pytest -q

poc:            ## kind + Calico + Agent Sandbox + OpenShell (laptop or CI)
	bash e2e/up.sh

e2e:            ## hostile-agent security suite against the running gateway
	bash e2e/run.sh

poc-down:
	bash e2e/down.sh

eks-up:         ## needs AWS credentials for a personal lab account
	cd infra/eks/terraform && terraform init && terraform apply
	aws eks update-kubeconfig --name $$(terraform -chdir=infra/eks/terraform output -raw cluster_name) --region $$(terraform -chdir=infra/eks/terraform output -raw region)
	bash infra/eks/install.sh

eks-test:
	TARGET=eks OSLAB_DRIVER_CONFIG=e2e/eks-driver-config.json OSLAB_SANDBOX_IMAGE=$$(cat .work/sandbox-image-ref) bash e2e/run.sh

eks-down:
	cd infra/eks/terraform && terraform destroy
