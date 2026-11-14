"""Dedicated disposable PVC: create, write, read in another Pod, request deletion."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from kfp import compiler, dsl, kubernetes, Client
IMAGE = os.environ.get('LAB_IMAGE', 'localhost:5002/ch9-lab:v1')

@dsl.component(base_image=IMAGE, install_kfp_package=False)
def manage_volume(name: str, delete: bool = False) -> str:
    import json
    import ssl
    import urllib.request
    from pathlib import Path
    service = Path('/var/run/secrets/kubernetes.io/serviceaccount')
    namespace = (service / 'namespace').read_text()
    url = 'https://kubernetes.default.svc/api/v1/namespaces/' + namespace + '/persistentvolumeclaims'
    body = {'apiVersion': 'v1', 'kind': 'PersistentVolumeClaim', 'metadata': {'name': name},
            'spec': {'accessModes': ['ReadWriteOnce'], 'storageClassName': 'standard',
                     'resources': {'requests': {'storage': '64Mi'}}}}
    request = urllib.request.Request(url + ('/' + name if delete else ''),
        data=None if delete else json.dumps(body).encode(), method='DELETE' if delete else 'POST',
        headers={'Authorization': 'Bearer ' + (service / 'token').read_text(), 'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, context=ssl.create_default_context(cafile=str(service / 'ca.crt'))) as response:
        print('PVC API status:', response.status, flush=True)
    return name

@dsl.component(base_image=IMAGE, install_kfp_package=False)
def write_file() -> str:
    import hashlib
    from pathlib import Path
    value = b'chapter-9 shared PVC verification\n'
    Path('/shared/evidence.txt').write_bytes(value)
    return hashlib.sha256(value).hexdigest()

@dsl.component(base_image=IMAGE, install_kfp_package=False)
def read_file(expected: str):
    import hashlib
    from pathlib import Path
    actual = hashlib.sha256(Path('/shared/evidence.txt').read_bytes()).hexdigest()
    assert actual == expected, (actual, expected)
    print('PVC read verified: ' + actual, flush=True)

@dsl.pipeline(name='chapter-9-pvc-lifecycle')
def pipeline(pvc_name: str):
    volume = manage_volume(name=pvc_name)
    writer = write_file()
    kubernetes.mount_pvc(writer, pvc_name=volume.output, mount_path='/shared')
    reader = read_file(expected=writer.output)
    kubernetes.mount_pvc(reader, pvc_name=volume.output, mount_path='/shared')
    cleanup = manage_volume(name=volume.output, delete=True).after(reader)
    for task in (volume, writer, reader, cleanup):
        task.set_caching_options(False)

if __name__ == '__main__':
    out = Path(__file__).parent / 'outputs/pvc-lifecycle'
    out.mkdir(parents=True, exist_ok=True)
    compiler.Compiler().compile(pipeline, str(out / 'pipeline.yaml'))
    name = 'ch9-lifecycle-' + datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    run = Client(host='http://127.0.0.1:8080').create_run_from_pipeline_package(str(out / 'pipeline.yaml'), arguments={'pvc_name': name}, experiment_name='chapter-9', run_name=name, enable_caching=False)
    (out / 'run.json').write_text(json.dumps({'run_id': run.run_id, 'pvc_name': name}, indent=2))
    print(run.run_id)
