"""Deployment script for self-hosted Supabase in Russia."""
import subprocess
import shutil
import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent


def ensure_docker():
    if not shutil.which("docker"):
        print("❌ Docker not found. Install first:")
        print("   curl -fsSL https://get.docker.com | sh")
        raise SystemExit(1)
    if not shutil.which("docker compose"):
        print("❌ Docker Compose v2 not found.")
        raise SystemExit(1)


def generate_secrets():
    """Generate random secrets if .env doesn't exist."""
    env_file = SCRIPT_DIR / ".env.russia"
    if env_file.exists():
        print("✔ .env.russia already exists")
        return

    import secrets
    postgres_pass = secrets.token_urlsafe(64)
    jwt_secret = secrets.token_urlsafe(32)[:32]

    template = f"""# Auto-generated secrets — COPY THIS FILE AND EDIT HOST
POSTGRES_PASSWORD={postgres_pass}
API_EXTERNAL_URL=http://YOUR_SERVER_IP:8000
SITE_URL=http://YOUR_SERVER_IP:3000
JWT_SECRET={jwt_secret}
"""
    env_file.write_text(template)
    print("✔ Generated .env.russia — EDIT THIS FILE and set YOUR_SERVER_IP")


def deploy():
    ensure_docker()
    generate_secrets()

    print("Deploying self-hosted Supabase for Russia...")
    subprocess.run(
        ["docker", "compose", "-f", "docker-compose.russia.yml", "up", "-d"],
        cwd=SCRIPT_DIR,
        check=True,
    )

    print("\n✅ Done!")
    print(f"   Kong Gateway:   http://localhost:8000")
    print(f"   PostgREST API:  http://localhost:3000")
    print(f"   Auth (GoTrue):  http://localhost:9999")
    print("\nConfigure Content Producer:")
    print("   SUPABASE_RUSSIA_URL=http://your-server:8000")
    print("   SUPABASE_RUSSIA_SERVICE_KEY=\u003cservice_role key from GoTrue\u003e")


def stop():
    subprocess.run(
        ["docker", "compose", "-f", "docker-compose.russia.yml", "down"],
        cwd=SCRIPT_DIR,
        check=True,
    )
    print("✅ Stopped")


def logs():
    subprocess.run(
        ["docker", "compose", "-f", "docker-compose.russia.yml", "logs", "-f"],
        cwd=SCRIPT_DIR,
        check=False,
    )


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Deploy self-hosted Supabase in Russia")
    parser.add_argument("command", choices=["deploy", "stop", "logs"], default="deploy")
    args = parser.parse_args()

    if args.command == "deploy":
        deploy()
    elif args.command == "stop":
        stop()
    elif args.command == "logs":
        logs()
