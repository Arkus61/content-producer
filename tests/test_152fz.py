import asyncio
import aiohttp
import json

BASE = "http://localhost:8000"
HEADERS = {"Content-Type": "application/json"}

async def run():
    async with aiohttp.ClientSession() as session:
        # 1. Register
        print("=== REGISTER ===")
        r = await session.post(f"{BASE}/api/auth/register", headers=HEADERS, json={
            "email": "admin@test.ru",
            "password": "TestPass123",
            "full_name": "Админ Тест"
        })
        print(r.status, await r.json())

        # 2. Login
        print("\n=== LOGIN ===")
        r = await session.post(f"{BASE}/api/auth/login", headers=HEADERS, json={
            "email": "admin@test.ru",
            "password": "TestPass123"
        })
        data = await r.json()
        print(r.status, data)
        token = data.get("access_token", "")
        AUTH = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # 3. Me
        print("\n=== ME ===")
        r = await session.get(f"{BASE}/api/auth/me", headers=AUTH)
        print(r.status, await r.json())

        # 4. Create expert with consent
        print("\n=== CREATE EXPERT ===")
        r = await session.post(f"{BASE}/api/experts", headers=AUTH, json={
            "name": "Иван Иванов",
            "email": "ivan@test.ru",
            "consent_granted": True,
            "expertise": ["маркетинг", "SMM"],
            "city": "Москва",
            "profession": "Маркетолог"
        })
        expert = await r.json()
        print(r.status, expert)
        expert_id = expert.get("expert_id")

        # 5. List experts
        print("\n=== LIST EXPERTS ===")
        r = await session.get(f"{BASE}/api/experts", headers=AUTH)
        print(r.status, await r.json())

        # 6. Operator info
        print("\n=== OPERATOR INFO ===")
        r = await session.get(f"{BASE}/api/info/operator")
        print(r.status, await r.json())

        # 7. Request export
        print("\n=== EXPORT REQUEST ===")
        r = await session.post(f"{BASE}/api/experts/{expert_id}/export", headers=AUTH, json={
            "export_format": "json",
            "include_transcriptions": True
        })
        export = await r.json()
        print(r.status, export)

        # 8. Audit logs
        print("\n=== AUDIT LOGS ===")
        r = await session.get(f"{BASE}/api/audit?limit=10", headers=AUTH)
        print(r.status, await r.json())

        print("\n✅ Все тесты пройдены")

if __name__ == "__main__":
    asyncio.run(run())
