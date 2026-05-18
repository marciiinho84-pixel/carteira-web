"""
Script de instalação inicial da Carteira Clean.

Como usar:
  1. Abra o Terminal (Ctrl + Alt + T)
  2. Vá até a pasta onde colocou os arquivos
  3. Digite: python3 instalar.py

Isso só precisa ser feito UMA VEZ. Depois, basta rodar:
  python3 atualizar_carteira.py

Para atualizar a planilha sempre que quiser.
"""
import subprocess
import sys

DEPS = ["yfinance", "pandas", "openpyxl", "requests", "numpy"]

print("=" * 65)
print("  CARTEIRA CLEAN — INSTALAÇÃO INICIAL")
print("=" * 65)
print()

# Verifica Python
print(f"  Python detectado: {sys.version.split()[0]}")
print(f"  Caminho: {sys.executable}")
print()

# Verifica pip
print("  Verificando pip...")
try:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "--version"],
        capture_output=True, text=True, timeout=10
    )
    if result.returncode == 0:
        print(f"  ✓ pip OK: {result.stdout.strip()}")
    else:
        print("  ⚠ pip não encontrado — vou tentar instalar...")
        subprocess.run(
            ["sudo", "apt", "install", "-y", "python3-pip"],
            check=False
        )
except Exception as e:
    print(f"  ⚠ Erro: {e}")
    print("  Tente rodar manualmente: sudo apt install python3-pip")
    sys.exit(1)
print()

# Instala cada dependência
print(f"  Instalando {len(DEPS)} pacotes Python...")
print(f"  ({', '.join(DEPS)})")
print()

ok = 0
falhas = []
for dep in DEPS:
    print(f"    [{ok+len(falhas)+1}/{len(DEPS)}] {dep}...", end=" ", flush=True)
    try:
        # Tenta primeiro com --break-system-packages (Ubuntu 23+)
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", dep,
             "--break-system-packages", "--user", "--quiet", "--upgrade"],
            capture_output=True, text=True, timeout=180
        )
        if result.returncode != 0:
            # Fallback: sem --break-system-packages (Ubuntu mais antigo)
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", dep,
                 "--user", "--quiet", "--upgrade"],
                capture_output=True, text=True, timeout=180
            )
        if result.returncode == 0:
            print("✓")
            ok += 1
        else:
            err = (result.stderr or result.stdout).strip().split("\n")[-1][:80]
            print(f"✗ ({err})")
            falhas.append(dep)
    except Exception as e:
        print(f"✗ ({e})")
        falhas.append(dep)

# Verifica importação
print()
print("  Verificando se os pacotes foram instalados...")
for dep in DEPS:
    nome_modulo = "yfinance" if dep == "yfinance" else dep
    try:
        __import__(nome_modulo)
        print(f"    ✓ {dep} importa OK")
    except ImportError:
        print(f"    ✗ {dep} NÃO importa")

print()
print("=" * 65)
if not falhas:
    print("  ✓ INSTALAÇÃO CONCLUÍDA COM SUCESSO!")
    print()
    print("  Agora você pode rodar o cálculo da carteira:")
    print()
    print("    python3 atualizar_carteira.py")
    print()
else:
    print(f"  ⚠ INSTALAÇÃO COM {len(falhas)} FALHAS: {', '.join(falhas)}")
    print()
    print("  Tente rodar manualmente:")
    print(f"    pip3 install {' '.join(falhas)} --user --break-system-packages")
    print()
print("=" * 65)
