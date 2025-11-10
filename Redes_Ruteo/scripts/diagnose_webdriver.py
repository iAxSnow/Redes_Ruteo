#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de diagnóstico para WebDriver y Chrome/Chromium.
Ayuda a identificar problemas de instalación y configuración.
"""

import sys
import subprocess
import os
from pathlib import Path

def run_command(cmd):
    """Run a command and return output"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return -1, "", str(e)

def check_chrome_installed():
    """Check if Chrome/Chromium is installed"""
    print("\n" + "="*60)
    print("1. Verificando instalación de Chrome/Chromium")
    print("="*60)
    
    commands = [
        ("chromium-browser --version", "Chromium"),
        ("google-chrome --version", "Google Chrome"),
        ("chromium --version", "Chromium (alt)"),
        ("/usr/bin/chromium-browser --version", "Chromium (path)"),
    ]
    
    found = False
    for cmd, name in commands:
        code, stdout, stderr = run_command(cmd)
        if code == 0 and stdout:
            print(f"✓ {name} encontrado: {stdout}")
            found = True
        else:
            print(f"✗ {name} no encontrado")
    
    if not found:
        print("\n❌ PROBLEMA: Chrome/Chromium no está instalado")
        print("\nSOLUCIÓN:")
        print("  sudo apt-get update")
        print("  sudo apt-get install -y chromium-browser")
        return False
    
    print("\n✓ Chrome/Chromium está instalado correctamente")
    return True

def check_chromedriver_installed():
    """Check if ChromeDriver is installed"""
    print("\n" + "="*60)
    print("2. Verificando instalación de ChromeDriver")
    print("="*60)
    
    commands = [
        ("chromedriver --version", "ChromeDriver"),
        ("/usr/bin/chromedriver --version", "ChromeDriver (path)"),
    ]
    
    found = False
    for cmd, name in commands:
        code, stdout, stderr = run_command(cmd)
        if code == 0 and stdout:
            print(f"✓ {name} encontrado: {stdout}")
            found = True
        else:
            print(f"✗ {name} no encontrado")
    
    if not found:
        print("\n❌ PROBLEMA: ChromeDriver no está instalado")
        print("\nSOLUCIÓN:")
        print("  sudo apt-get update")
        print("  sudo apt-get install -y chromium-chromedriver")
        return False
    
    print("\n✓ ChromeDriver está instalado correctamente")
    return True

def check_selenium_installed():
    """Check if Selenium is installed"""
    print("\n" + "="*60)
    print("3. Verificando instalación de Selenium")
    print("="*60)
    
    try:
        import selenium
        print(f"✓ Selenium instalado: versión {selenium.__version__}")
        return True
    except ImportError:
        print("✗ Selenium no está instalado")
        print("\n❌ PROBLEMA: Selenium no está instalado")
        print("\nSOLUCIÓN:")
        print("  pip install selenium")
        return False

def test_webdriver():
    """Test if WebDriver can start"""
    print("\n" + "="*60)
    print("4. Probando inicialización de WebDriver")
    print("="*60)
    
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.common.exceptions import WebDriverException, SessionNotCreatedException
        
        print("Intentando iniciar Chrome en modo headless...")
        
        chrome_options = Options()
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        
        try:
            driver = webdriver.Chrome(options=chrome_options)
            print("✓ WebDriver iniciado correctamente")
            
            # Try to navigate to a test page
            print("Probando navegación a página de prueba...")
            driver.get("https://www.google.com")
            print(f"✓ Navegación exitosa, título: {driver.title[:50]}...")
            
            driver.quit()
            print("✓ WebDriver cerrado correctamente")
            print("\n✅ TODO FUNCIONA CORRECTAMENTE")
            return True
            
        except SessionNotCreatedException as e:
            error_msg = str(e)
            print(f"✗ Error al crear sesión de WebDriver")
            print(f"\nError completo:\n{error_msg}\n")
            
            if "Chrome version" in error_msg or "ChromeDriver" in error_msg:
                print("❌ PROBLEMA: Incompatibilidad de versiones Chrome/ChromeDriver")
                print("\nSOLUCIÓN:")
                print("  sudo apt-get update")
                print("  sudo apt-get upgrade chromium-browser chromium-chromedriver")
            elif "Chrome failed to start" in error_msg or "Chrome instance exited" in error_msg:
                print("❌ PROBLEMA: Chrome no puede iniciar (faltan dependencias)")
                print("\nSOLUCIÓN:")
                print("  # Instalar dependencias necesarias:")
                print("  sudo apt-get install -y libnss3 libgconf-2-4 libfontconfig1")
                print("  # O reinstalar Chrome:")
                print("  sudo apt-get remove --purge chromium-browser chromium-chromedriver")
                print("  sudo apt-get install -y chromium-browser chromium-chromedriver")
            else:
                print("❌ PROBLEMA: Error desconocido al iniciar WebDriver")
                print("\nVerifica el log completo arriba para más detalles")
            
            return False
            
        except WebDriverException as e:
            print(f"✗ Error de WebDriver: {e}")
            return False
            
    except ImportError as e:
        print(f"✗ No se pudo importar Selenium: {e}")
        return False
    except Exception as e:
        print(f"✗ Error inesperado: {e}")
        return False

def check_environment():
    """Check environment variables and system info"""
    print("\n" + "="*60)
    print("5. Información del sistema")
    print("="*60)
    
    # Display variable
    display = os.environ.get('DISPLAY', 'No configurado')
    print(f"DISPLAY: {display}")
    if display == 'No configurado':
        print("  ℹ️  Esto es normal en modo headless")
    
    # Check if running in container
    code, stdout, stderr = run_command("cat /proc/1/cgroup 2>/dev/null | grep -q docker")
    if code == 0:
        print("Entorno: Docker/Container detectado")
        print("  ℹ️  Asegúrate de usar --no-sandbox y --disable-dev-shm-usage")
    else:
        print("Entorno: Sistema normal (no container)")
    
    # OS info
    code, stdout, stderr = run_command("lsb_release -d 2>/dev/null")
    if code == 0:
        print(f"Sistema operativo: {stdout}")

def main():
    """Run all diagnostics"""
    print("\n" + "="*60)
    print("DIAGNÓSTICO DE WEBDRIVER PARA WAZE")
    print("="*60)
    print("\nEste script verificará la configuración de WebDriver")
    print("y ayudará a identificar problemas.\n")
    
    results = []
    
    # Run all checks
    results.append(("Chrome/Chromium", check_chrome_installed()))
    results.append(("ChromeDriver", check_chromedriver_installed()))
    results.append(("Selenium", check_selenium_installed()))
    
    # Only test WebDriver if prerequisites are met
    if all(r[1] for r in results):
        results.append(("WebDriver Test", test_webdriver()))
    else:
        print("\n⚠️  Saltando prueba de WebDriver (faltan prerequisitos)")
        results.append(("WebDriver Test", False))
    
    check_environment()
    
    # Summary
    print("\n" + "="*60)
    print("RESUMEN")
    print("="*60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ OK" if passed else "❌ FALLO"
        print(f"{status:10} {name}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("✅ TODO ESTÁ CONFIGURADO CORRECTAMENTE")
        print("\nEl sistema debería poder recolectar datos reales de Waze.")
        print("Ejecuta: python amenazas/waze_incidents_parallel_adaptive.py")
    else:
        print("❌ HAY PROBLEMAS DE CONFIGURACIÓN")
        print("\nSigue las soluciones indicadas arriba para cada problema.")
        print("Después de aplicar las correcciones, ejecuta este script nuevamente.")
    print("="*60 + "\n")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
