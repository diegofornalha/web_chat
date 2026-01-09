#!/usr/bin/env python3
import uvicorn
from claude_mini_sdk.config import SERVER_CONFIG

def main():
    print("\n" + "=" * 60)
    print("🚀 Claude E2B API - Versão Modular 2.0")
    print("=" * 60)
    print(f"\n📍 Acesse: http://localhost:{SERVER_CONFIG['port']}")
    print("🔒 Sandbox novo a cada request (isolamento total)")
    print("🛡️  CORS configurado (apenas localhost)")
    print("🔑 Token via env var (não hardcoded)")
    print("=" * 60 + "\n")

    uvicorn.run(
        "web_chat.app:app",  # Import path do módulo
        host=SERVER_CONFIG["host"],
        port=SERVER_CONFIG["port"],
        reload=False  # True em desenvolvimento, False em produção
    )

if __name__ == "__main__":
    main()
