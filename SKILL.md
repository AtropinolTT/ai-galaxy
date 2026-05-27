---
name: ai-galaxy
description: |
  AI Galaxy (智星云) cloud platform management skill for GPU compute instances.
  TRIGGER whenever the user mentions:
  - "AI Galaxy", "智星云", "gpu.ai-galaxy.cn"
  - "cloud GPU", "租用GPU", "云主机", "云容器"
  - "run job on cloud", "submit job", "训练" (training)
  - "SSH to cloud", "SFTP upload", "connect to server"
  - "manage cloud instance", "restart instance", "check GPU status"
  - Any task involving the AI Galaxy platform for computation
  This skill enables Claude to establish SSH/SFTP connections, manage cloud compute instances,
  submit and monitor training jobs, and transfer files using Python3.
---

# AI Galaxy Cloud Platform Management

AI Galaxy (智星云) provides GPU cloud computing resources at gpu.ai-galaxy.cn. This skill
enables agents to manage instances, run jobs, and transfer files.

## Connection Setup

### SSH Address

The user must provide the instance IP and SSH port for their specific instance.

### Python SSH/SFTP Connection

Use the `ssh_connector.py` helper script. **Path: `<skill-base>/scripts/ssh_connector.py`**

```python
import sys
sys.path.insert(0, '<skill-base>/scripts')
from ssh_connector import SSHConnection

conn = SSHConnection(
    host='<INSTANCE_IP>',      # user-provided IP
    port=<SSH_PORT>,           # user-provided port
    username='root',
    password='<PASSWORD>'       # user-provided password
)
```

### Direct SSH Command

```bash
ssh root@<INSTANCE_IP> -p <SSH_PORT>
```

## Instance Management via API

Base URL: `https://api.ai-galaxy.cn`

Authentication: AccessKey signature (see API docs for signing algorithm)

### Key Endpoints

| Operation | Method | Endpoint |
|----------|--------|----------|
| Get instance list | GET | `/api/v1/instances` |
| Get instance status | GET | `/api/v1/instances/{id}` |
| Start/Stop instance | POST | `/api/v1/instances/{id}/action` |
| Create instance | POST | `/api/v1/instances` |
| Resize instance | PUT | `/api/v1/instances/{id}/resize` |
| Renew instance | POST | `/api/v1/instances/{id}/renew` |

## Running Jobs

### IMPORTANT: Use `invoke_shell()` for Training Jobs

**Critical discovery:** `exec_command()` via `paramiko.Transport.open_session()` does not work reliably for launching background training jobs. Shell redirection and nohup fail silently — the process exits immediately with "nohup: 忽略输入" error. **Use `invoke_shell()` instead:**

```python
import paramiko
import time
client = paramiko.SSHClient()
client.load_system_host_keys()
client.connect('<INSTANCE_IP>', port=<SSH_PORT>, username='root', password='<PASSWORD>', timeout=20)

channel = client.invoke_shell()
time.sleep(1)
channel.send('cd <WORKING_DIR>\n')
time.sleep(1)
channel.send('source <CONDA_PREFIX>/etc/profile.d/conda.sh\n')
time.sleep(1)
channel.send('conda activate <ENV_NAME>\n')
time.sleep(1)
channel.send('CUDA_VISIBLE_DEVICES=<GPU_ID> nohup python -u <TRAIN_SCRIPT>.py > <LOG_FILE>.txt 2>&1 &\n')
time.sleep(2)
channel.send('echo "Started at $(date)"\n')
time.sleep(1)
output = channel.recv(65536).decode()
channel.close()
client.close()
```

### Monitoring Running Jobs

After starting a job, poll status with `exec_command()` via `Transport.open_session()`:

```python
import paramiko
client = paramiko.SSHClient()
client.load_system_host_keys()
client.connect('<INSTANCE_IP>', port=<SSH_PORT>, username='root', password='<PASSWORD>', timeout=20)

transport = client.get_transport()
channel = transport.open_session()
channel.get_pty()
channel.exec_command('ps aux | grep <TRAIN_PROCESS> 2>/dev/null | grep -v grep; echo "---"; nvidia-smi --query-gpu=utilization.gpu,utilization.memory --format=csv 2>/dev/null; echo "---LOG---"; tail -10 <WORKING_DIR>/<LOG_FILE>.txt 2>/dev/null')
out = []
while True:
    if channel.exit_status_ready(): break
    if channel.recv_ready(): out.append(channel.recv(4096))
while channel.recv_ready(): out.append(channel.recv(4096))
print(b''.join(out).decode())
channel.close()
client.close()
```

### Using screen for Long-Running Tasks

```bash
screen -S training
python train.py --model resnet50 --epochs 100
# Detach: press Ctrl+A, then D
# List sessions: screen -ls
# Reattach: screen -r training
# Terminate: reattach then Ctrl+D
```

Note: `screen` may not be installed. Use `invoke_shell()` method instead.

### Docker GPU Jobs

```bash
docker pull pytorch/pytorch:1.9.0-cuda10.2-cudnn7-runtime
docker run -it --gpus=all pytorch/pytorch:1.9.0-cuda10.2-cudnn7-runtime bash
docker cp /local/file.txt <container_name>:/workspace/file.txt
```

### Monitoring GPU Status

```bash
nvidia-smi
watch nvidia-smi
```

## File Transfer

### SFTP via Python

```python
from ssh_connector import SFTPConnection

sftp = SFTPConnection(
    host='<INSTANCE_IP>',
    port=<SSH_PORT>,
    username='root',
    password='<PASSWORD>'
)

sftp.upload('/local/path/file.txt', '/remote/workspace/path/file.txt')
sftp.download('/remote/workspace/path/file.txt', '/local/path/')
sftp.listdir('/remote/workspace/')
```

### SCP Command Line

```bash
scp -P <SSH_PORT> /local/file.txt root@<INSTANCE_IP>:/remote/workspace/
scp -P <SSH_PORT> root@<INSTANCE_IP>:/remote/workspace/file.txt /local/path/
```

## Cloud-Specific Path Reference

Typical working directory: `/root/workspace/`

Key paths to verify when troubleshooting:
- Training scripts: `<WORKING_DIR>/<PROJECT_DIR>/`
- Model weights: `<WORKING_DIR>/<MODEL_FILE>.pt`
- LMDB data: `<WORKING_DIR>/<DATA>.lmdb`
- Dict file: `<WORKING_DIR>/dict.txt`

## Common Workflows

### 1. Submit Training Job

1. Connect via SSH using `invoke_shell()`
2. Upload training code via SFTP to `<WORKING_DIR>/<PROJECT_DIR>/`
3. Ensure model weights exist: `ls -la <WORKING_DIR>/*.pt`
4. Run training: `CUDA_VISIBLE_DEVICES=<GPU_ID> nohup python -u <SCRIPT>.py > <LOG>.txt 2>&1 &`
5. Disconnect — job continues in background
6. Reconnect later: `tail <LOG>.txt`

### 2. Monitor Running Job

Poll with `exec_command()` via `Transport.open_session()`:
```bash
nvidia-smi --query-gpu=utilization.gpu,utilization.memory --format=csv
ps aux | grep <TRAIN_PROCESS> | grep -v grep
tail -10 <WORKING_DIR>/<LOG>.txt
```

### 3. Transfer Large Files

Large files (100MB+) take time. Upload via SFTP:
```python
sftp.put('/local/model.pt', '/remote/workspace/model.pt')
```

## Troubleshooting

### SSH Connection Issues

- **"REMOTE HOST IDENTIFICATION HAS CHANGED"**: Delete `known_hosts` entry or run `ssh-keygen -R <host>`
- **Connection refused**: Check SSH port and instance is running
- **Permission denied**: Verify password is correct

### Instance Issues

- **Instance stuck**: Restart via API or control panel
- **GPU unavailable**: Check nvidia-smi output
- **Out of memory**: Use `top` and `nvidia-smi` to monitor

### Disk Space Issues

- **"No space left on device"**: Clear caches:
  ```bash
  rm -rf /root/.cache/pip /root/.cache/huggingface /root/.cache/JetBrains
  ```
- Keep at least 5GB free for checkpoints

### Missing Modules

- **`ModuleNotFoundError: No module named 'datasets'`**: Run `pip install datasets`
- **`ModuleNotFoundError: No module named 'data_process'`**: Ensure working dir contains `data_process/` directory or symlink

### Training Won't Start

- If `exec_command()` fails to start background jobs, switch to `invoke_shell()` method
- Check log file: `cat <WORKING_DIR>/<LOG>.txt`
- Verify model weights exist: `ls -la <WORKING_DIR>/*.pt`