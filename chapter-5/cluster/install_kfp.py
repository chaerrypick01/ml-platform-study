"""Install the guide's KFP standalone into the isolated ch5-lab kind cluster."""
from pathlib import Path
import subprocess
import time

HERE = Path(__file__).resolve().parent
CH5 = HERE.parent
CONFIG = CH5 / '.kube/config'
MANIFESTS = CH5 / '.cache/kfp-2.4.1/manifests/kustomize'


def kubectl(*args):
    subprocess.run(['kubectl', '--kubeconfig', str(CONFIG), '--context', 'kind-ch5-lab', *map(str, args)], check=True)


if __name__ == '__main__':
    kubectl('get', 'nodes')
    kubectl('apply', '-k', MANIFESTS / 'cluster-scoped-resources')
    kubectl('wait', '--for=condition=established', '--timeout=120s', 'crd/applications.app.k8s.io')
    for attempt in range(3):
        try:
            kubectl('apply', '-k', MANIFESTS / 'env/platform-agnostic')
            break
        except subprocess.CalledProcessError:
            if attempt == 2:
                raise
            time.sleep(10)
    for deployment, patch in [('minio', 'object-store-patch.yaml'), ('workflow-controller', 'executor-patch.yaml')]:
        kubectl('-n', 'kubeflow', 'patch', 'deployment', deployment, '--patch-file', HERE / patch)
    for deployment in ['minio', 'mysql', 'metadata-grpc-deployment', 'ml-pipeline', 'workflow-controller', 'ml-pipeline-ui']:
        kubectl('-n', 'kubeflow', 'rollout', 'status', f'deployment/{deployment}', '--timeout=900s')
