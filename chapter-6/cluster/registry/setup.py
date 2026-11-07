"""Connect the existing ch5-lab node to the local lab registry."""
import json
import subprocess


def run(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, **kwargs)


def main():
    name = "ch6-registry"
    existing = subprocess.run(["docker", "inspect", name], capture_output=True, text=True)
    if existing.returncode:
        run("docker", "run", "-d", "--restart=unless-stopped", "-p",
            "127.0.0.1:5002:5000", "--network", "kind", "--name", name,
            "-v", "ch6-registry-data:/var/lib/registry", "registry:3")
    else:
        info = json.loads(existing.stdout)[0]
        if "kind" not in info["NetworkSettings"]["Networks"]:
            run("docker", "network", "connect", "kind", name)
        if not info["State"]["Running"]:
            run("docker", "start", name)
    node = "ch5-lab-control-plane"
    config = run("docker", "exec", node, "cat", "/etc/containerd/config.toml",
                 capture_output=True).stdout
    if "config_path" not in config:
        config += '\n[plugins."io.containerd.grpc.v1.cri".registry]\n  config_path = "/etc/containerd/certs.d"\n'
        run("docker", "exec", "-i", node, "cp", "/dev/stdin",
            "/etc/containerd/config.toml", input=config)
        run("docker", "exec", node, "systemctl", "restart", "containerd")
    directory = "/etc/containerd/certs.d/localhost:5002"
    run("docker", "exec", node, "mkdir", "-p", directory)
    run("docker", "exec", "-i", node, "cp", "/dev/stdin", directory + "/hosts.toml",
        input='[host."http://ch6-registry:5000"]\n  capabilities = ["pull", "resolve"]\n')


if __name__ == "__main__":
    main()
