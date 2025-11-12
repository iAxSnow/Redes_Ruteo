#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de diagnóstico para WebDriver y Firefox/GeckoDriver.
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

def check_firefox_installed():
    """Check if Firefox is installed"""
    print("\n" + "="*60)
    print("1. Verificando instalación de Firefox")
    print("="*60)
    
    commands = [
        ("firefox-esr --version", "Firefox ESR"), # Prioridad #1
        ("firefox --version", "Firefox"),
        ("/usr/bin/firefox-esr --version", "Firefox ESR (path)"),
        ("/usr/bin/firefox --version", "Firefox (path)"),
        ("snap run firefox --version 2>/dev/null", "Firefox (snap)"),
    ]
    
    found = False
    firefox_path = None
    for cmd, name in commands:
        code, stdout, stderr = run_command(cmd)
        if code == 0 and stdout:
            print(f"✓ {name} encontrado: {stdout}")
            found = True
            if not firefox_path:
                firefox_path = cmd.split()[0]
        else:
            print(f"✗ {name} no encontrado")
    
    if not found:
        print("\n❌ PROBLEMA: Firefox no está instalado")
        print("\nSOLUCIÓN:")
        print("  (Sigue los pasos del PPA de Mozilla para instalar firefox-esr)")
        return False
    
    print("\n✓ Firefox está instalado correctamente")
    if firefox_path:
        print(f"   Ubicación: {firefox_path}")
    return True

def check_geckodriver_installed():
    """Check if GeckoDriver is installed"""
    print("\n" + "="*60)
    print("2. Verificando instalación de GeckoDriver")
    print("="*60)
    
    commands = [
        ("geckodriver --version", "GeckoDriver"),
        ("/usr/bin/geckodriver --version", "GeckoDriver (path)"),
        ("/usr/local/bin/geckodriver --version", "GeckoDriver (manual path)"),
    ]
    
    found = False
    driver_path = None
    for cmd, name in commands:
        code, stdout, stderr = run_command(cmd)
        if code == 0 and (stdout or stderr):  # geckodriver may output to stderr
            output = stdout if stdout else stderr
            print(f"✓ {name} encontrado: {output.split(chr(10))[0]}")  # First line only
            found = True
            if not driver_path:
                driver_path = cmd.split()[0]
        else:
            print(f"✗ {name} no encontrado")
    
    if not found:
        print("\n❌ PROBLEMA: GeckoDriver no está instalado")
        print("\nSOLUCIÓN:")
        print("  (Sigue los pasos para instalar geckodriver manualmente desde GitHub)")
        return False
    
    print("\n✓ GeckoDriver está instalado correctamente")
    if driver_path:
        print(f"   Ubicación: {driver_path}")
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
        print("\nSOLUCICIÓN:")
        print("  pip install selenium")
        return False

def test_webdriver():
    """Test if WebDriver can start"""
    print("\n" + "="*60)
    print("4. Probando inicialización de WebDriver (Firefox)")
    print("="*60)
    
    try:
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service
        from selenium.common.exceptions import WebDriverException, SessionNotCreatedException
        
        print("Intentando iniciar Firefox en modo headless...")
        
        # --- INICIO DE LA CORRECCIÓN ---
        # Reordenado para priorizar 'firefox-esr'
        firefox_binary = None
        possible_paths = [
            '/usr/bin/firefox-esr',     # <-- Prioridad #1 (del PPA de Mozilla)
            '/usr/bin/firefox',         # <-- Prioridad #2 (dummy snap)
            '/snap/bin/firefox',
            '/usr/local/bin/firefox',
            '/usr/local/bin/firefox-esr'
        ]
        
        for path in possible_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                firefox_binary = path
                print(f"  Detectado Firefox en: {path}")
                break
        
        if not firefox_binary:
            # Try via PATH
            code, stdout, _ = run_command("which firefox-esr")
            if code == 0 and stdout.strip():
                firefox_binary = stdout.strip()
                print(f"  Detectado Firefox ESR via PATH: {firefox_binary}")
            else:
                code, stdout, _ = run_command("which firefox")
                if code == 0 and stdout.strip():
                    firefox_binary = stdout.strip()
                    print(f"  Detectado Firefox via PATH: {firefox_binary}")
        # --- FIN DE LA CORRECCIÓN ---

        # Find GeckoDriver
        geckodriver_path = None
        code, stdout, _ = run_command("which geckodriver")
        if code == 0 and stdout.strip():
            geckodriver_path = stdout.strip()
            print(f"  Detectado GeckoDriver en: {geckodriver_path}")
        
        firefox_options = Options()
        firefox_options.add_argument('-headless')
        
        # Set binary location if found
        if firefox_binary:
            firefox_options.binary_location = firefox_binary
            print(f"  Configurando Firefox binary: {firefox_binary}")
        
        # Configure service if geckodriver found
        service = None
        if geckodriver_path:
            service = Service(executable_path=geckodriver_path)
            print(f"  Configurando GeckoDriver service: {geckodriver_path}")
        
        try:
            if service:
                driver = webdriver.Firefox(options=firefox_options, service=service)
            else:
                driver = webdriver.Firefox(options=firefox_options)
            print("✓ Firefox WebDriver iniciado correctamente")
            
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
            
            if "binary is not a firefox executable" in error_msg.lower():
                print("❌ PROBLEMA: El binario de Firefox no es válido o no se puede ejecutar")
                print(f"   Binario problemático: {firefox_binary}")
                print("\nCAUSA PROBABLE:")
                print("  - El path de arriba apunta al 'dummy snap installer' de Ubuntu.")
                print("\nSOLUCIÓN:")
                print("  1. Asegúrate de haber instalado Firefox desde el PPA de Mozilla:")
                print("     sudo add-apt-repository ppa:mozillateam/ppa")
                print("     sudo apt update && sudo apt install firefox-esr")
                print("  2. Verifica que '/usr/bin/firefox-esr' existe.")
            elif "geckodriver" in error_msg.lower():
                print("❌ PROBLEMA: GeckoDriver no encontrado o incompatible")
                print("\nSOLUCIÓN:")
                print("  (Sigue los pasos para instalar geckodriver manualmente desde GitHub)")
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
    else:
        code, stdout, _ = run_command("cat /proc/1/cgroup 2>/dev/null | grep -q 'workspaces'")
        if code == 0:
            print("Entorno: Codespace/Container detectado")
        else:
            print("Entorno: Sistema normal (no container)")
    
    # OS info
    code, stdout, stderr = run_command("lsb_release -d 2>/dev/null")
    if code == 0:
        print(f"Sistema operativo: {stdout}")

def main():
    """Run all diagnostics"""
    print("\n" + "="*60)
    print("DIAGNÓSTICO DE WEBDRIVER (FIREFOX) PARA WAZE")
    print("="*60)
    print("\nEste script verificará la configuración de Firefox WebDriver")
    print("y ayudará a identificar problemas.\n")
    
    results = []
    
    # Run all checks
    results.append(("Firefox", check_firefox_installed()))
    results.append(("GeckoDriver", check_geckodriver_installed()))
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
        print("\nEl sistema debería poder recolectar datos reales de Waze con Firefox.")
        print("Ejecuta: python amenazas/waze_incidents_parallel_adaptive.py")
    else:
        print("❌ HAY PROBLEMAS DE CONFIGURACIÓN")
        print("\nSigue las soluciones indicadas arriba para cada problema.")
        print("Si faltan, instala Firefox (ESR) y GeckoDriver (manual):")
    print("="*60 + "\n")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())