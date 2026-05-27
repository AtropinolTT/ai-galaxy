"""
AI Galaxy SSH/SFTP Connector

Python helper for establishing SSH/SFTP connections to AI Galaxy cloud instances.
Supports both password and SSH key authentication.

Usage:
    from ssh_connector import SSHConnection, SFTPConnection

    # Password auth
    ssh = SSHConnection(host='<INSTANCE_IP>', port=<SSH_PORT>, username='root', password='<PASSWORD>')
    output = ssh.execute('nvidia-smi')

    # SSH key auth
    ssh = SSHConnection(host='<INSTANCE_IP>', port=<SSH_PORT>, username='root', key_file='/path/to/key')

    # SFTP
    sftp = SFTPConnection(host='<INSTANCE_IP>', port=<SSH_PORT>, username='root', password='<PASSWORD>')
    sftp.upload('/local/file.txt', '/remote/file.txt')
"""

import paramiko
import io
from typing import Optional, List


class SSHConnection:
    """Context manager for SSH connections to AI Galaxy instances."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: Optional[str] = None,
        key_file: Optional[str] = None,
        passphrase: Optional[str] = None
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.key_file = key_file
        self.passphrase = passphrase
        self.client: Optional[paramiko.SSHClient] = None

    def __enter__(self):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        connect_kwargs = {
            'hostname': self.host,
            'port': self.port,
            'username': self.username,
        }

        if self.key_file:
            connect_kwargs['key_filename'] = self.key_file
            if self.passphrase:
                connect_kwargs['pkey'] = self._load_key_with_passphrase()
            else:
                connect_kwargs['key_filename'] = self.key_file
        elif self.password:
            connect_kwargs['password'] = self.password

        self.client.connect(**connect_kwargs)
        return self

    def _load_key_with_passphrase(self):
        """Load SSH key with passphrase."""
        if self.key_file:
            with open(self.key_file, 'r') as f:
                return paramiko.RSAKey.from_private_key(f, password=self.passphrase)
        return None

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            self.client.close()

    def execute(self, command: str, timeout: int = 30) -> str:
        """Execute a command and return stdout."""
        if not self.client:
            raise RuntimeError("Connection not open. Use 'with' statement.")

        stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()

        output = stdout.read().decode('utf-8', errors='replace')
        error = stderr.read().decode('utf-8', errors='replace')

        if exit_code != 0 and error:
            raise RuntimeError(f"Command failed with exit code {exit_code}: {error}")

        return output

    def execute_async(self, command: str) -> paramiko.Channel:
        """Execute a command without waiting for completion (for long-running tasks)."""
        if not self.client:
            raise RuntimeError("Connection not open. Use 'with' statement.")

        channel = self.client.get_transport().open_session()
        channel.exec_command(command)
        return channel


class SFTPConnection:
    """Context manager for SFTP connections to AI Galaxy instances."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: Optional[str] = None,
        key_file: Optional[str] = None,
        passphrase: Optional[str] = None
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.key_file = key_file
        self.passphrase = passphrase
        self.transport: Optional[paramiko.Transport] = None
        self.sftp: Optional[paramiko.SFTPClient] = None

    def __enter__(self):
        connect_kwargs = {
            'hostname': self.host,
            'port': self.port,
            'username': self.username,
        }

        if self.key_file:
            if self.passphrase:
                with open(self.key_file, 'r') as f:
                    pkey = paramiko.RSAKey.from_private_key(f, password=self.passphrase)
                connect_kwargs['pkey'] = pkey
            else:
                connect_kwargs['key_filename'] = self.key_file
        elif self.password:
            connect_kwargs['password'] = self.password

        self.transport = paramiko.Transport((self.host, self.port))
        self.transport.connect(**connect_kwargs)
        self.sftp = paramiko.SFTPClient.from_transport(self.transport)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.sftp:
            self.sftp.close()
        if self.transport:
            self.transport.close()

    def upload(self, local_path: str, remote_path: str):
        """Upload a file to the remote instance."""
        if not self.sftp:
            raise RuntimeError("Connection not open. Use 'with' statement.")
        self.sftp.put(local_path, remote_path)

    def download(self, remote_path: str, local_path: str):
        """Download a file from the remote instance."""
        if not self.sftp:
            raise RuntimeError("Connection not open. Use 'with' statement.")
        self.sftp.get(remote_path, local_path)

    def listdir(self, remote_path: str) -> List[str]:
        """List directory contents."""
        if not self.sftp:
            raise RuntimeError("Connection not open. Use 'with' statement.")
        return self.sftp.listdir(remote_path)

    def mkdir(self, remote_path: str):
        """Create a directory on the remote instance."""
        if not self.sftp:
            raise RuntimeError("Connection not open. Use 'with' statement.")
        self.sftp.mkdir(remote_path)

    def rmdir(self, remote_path: str):
        """Remove a directory on the remote instance."""
        if not self.sftp:
            raise RuntimeError("Connection not open. Use 'with' statement.")
        self.sftp.rmdir(remote_path)

    def remove(self, remote_path: str):
        """Remove a file on the remote instance."""
        if not self.sftp:
            raise RuntimeError("Connection not open. Use 'with' statement.")
        self.sftp.remove(remote_path)


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 3:
        print("Usage: python ssh_connector.py <host> <port> <username> [password|key_file]")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])
    username = sys.argv[3]

    # Simple test connection
    if len(sys.argv) >= 5:
        auth_param = sys.argv[4]
        if auth_param.startswith('/'):
            conn = SSHConnection(host=host, port=port, username=username, key_file=auth_param)
        else:
            conn = SSHConnection(host=host, port=port, username=username, password=auth_param)
    else:
        print("Please provide password or key file path")
        sys.exit(1)

    with conn:
        result = conn.execute('echo "Connection successful" && nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo "nvidia-smi not available"')
        print(result)