# AI Galaxy Skill

> Claude skill for managing GPU compute instances on [AI Galaxy (智星云)](https://gpu.ai-galaxy.cn) — run training jobs, transfer files, and monitor GPU status without leaving your terminal.

![AI Galaxy](https://img.shields.io/badge/AI%20Galaxy-GPU%20Cloud-6C63FF?style=flat-square)

## What This Does

- **Connect** to AI Galaxy GPU instances via SSH/SFTP
- **Launch** training jobs with proper background handling
- **Transfer** files between local machine and cloud
- **Monitor** GPU utilization and job logs
- **Manage** instances through the AI Galaxy API

## Quick Start

### 1. Connect to Your Instance

```python
import sys
sys.path.insert(0, 'scripts/')
from ssh_connector import SSHConnection

conn = SSHConnection(
    host='YOUR_INSTANCE_IP',
    port=YOUR_SSH_PORT,
    username='root',
    password='YOUR_PASSWORD'
)

with conn:
    print(conn.execute('nvidia-smi'))
```

### 2. Launch a Training Job

```python
# IMPORTANT: Use invoke_shell() instead of exec_command() for background jobs
channel = client.invoke_shell()
channel.send('cd /root/workspace/\n')
channel.send('conda activate myenv\n')
channel.send('CUDA_VISIBLE_DEVICES=0 nohup python -u train.py > train.log 2>&1 &\n')
```

### 3. Upload Training Data

```python
from ssh_connector import SFTPConnection

sftp = SFTPConnection(host='IP', port=PORT, username='root', password='PWD')
with sftp as s:
    s.upload('./data/train.lmdb', '/root/workspace/data/')
    s.upload('./model_weights.pt', '/root/workspace/')
```

### 4. Monitor Running Jobs

```python
# Poll GPU usage and check logs
output = conn.execute('''
    nvidia-smi --query-gpu=utilization.gpu,utilization.memory --format=csv
    tail -20 /root/workspace/train.log
''')
print(output)
```

## Installation

```bash
pip install paramiko
```

Then add the skill to your Claude configuration by placing the `ai-galaxy/` folder in your skills directory.

## File Structure

```
ai-galaxy/
├── SKILL.md              # Full documentation
├── README.md             # This file
└── scripts/
    └── ssh_connector.py  # SSH/SFTP helper classes
```

## Common Workflows

| Task | Command |
|------|---------|
| Start training | `nohup python -u train.py > log.txt 2>&1 &` |
| Check GPU | `nvidia-smi` |
| View logs | `tail -f train.log` |
| Upload files | `sftp.upload(local, remote)` |
| Free disk space | `rm -rf ~/.cache/pip ~/.cache/huggingface` |

## Troubleshooting

- **"REMOTE HOST IDENTIFICATION HAS CHANGED"** → Run `ssh-keygen -R <host>`
- **Job won't start in background** → Use `invoke_shell()` instead of `exec_command()`
- **Permission denied** → Verify password or switch to SSH key auth
- **Disk full** → Clear pip/huggingface caches

## Learn More

See [SKILL.md](SKILL.md) for complete API documentation and advanced usage examples.