#!/bin/bash

echo "[SHPD] Finalizando configuración. Pasando a modo Wi-Fi cliente..."

# 1) Incorporar la nueva configuración Wi-Fi
if [ -f "/tmp/wpa_supplicant.conf.tmp" ]; then
    echo "[SHPD] ✍️  Añadiendo nueva configuración de red..."
    sudo tee -a /etc/wpa_supplicant/wpa_supplicant.conf < /tmp/wpa_supplicant.conf.tmp > /dev/null
    sudo rm /tmp/wpa_supplicant.conf.tmp
else
    echo "[SHPD] ⚠️  No se encontró el archivo de configuración Wi-Fi temporal."
fi

# 2) Apagar el hotspot
echo "[SHPD] 📴  Apagando hotspot..."
sudo systemctl stop hostapd.service    dnsmasq.service

# 3) Deshabilitar y enmascarar servicios de hotspot para el arranque normal
echo "[SHPD] 🚫  Deshabilitando servicios de modo AP en el próximo arranque..."
sudo systemctl disable hostapd.service    dnsmasq.service
sudo systemctl mask    hostapd.service    dnsmasq.service

# 4) (Re)habilitar servicios de cliente Wi-Fi
echo "[SHPD] ✅  Habilitando servicios de cliente Wi-Fi..."
sudo systemctl unmask   wpa_supplicant.service dhcpcd.service
sudo systemctl enable   wpa_supplicant.service dhcpcd.service
sudo systemctl restart  wpa_supplicant.service dhcpcd.service

# 5) Reiniciar interfaz inalámbrica
echo "[SHPD] 🔄  Reiniciando interfaz wlan0..."
sudo ip link set wlan0 down
sleep 2
sudo ip link set wlan0 up
sleep 1

# 6) Conectarse a la red configurada
echo "[SHPD] 🌐  Iniciando wpa_supplicant y DHCP client..."
sudo wpa_supplicant -B -i wlan0 -c /etc/wpa_supplicant/wpa_supplicant.conf
sleep 5
sudo dhclient wlan0

# 7) Limpiar cualquier configuración estática previa
echo "[SHPD] 🧹  Limpiando configuración estática en /etc/dhcpcd.conf..."
sudo sed -i '/^interface wlan0$/,/^$/d' /etc/dhcpcd.conf

# 8) Eliminar marca de hotspot activo
echo "[SHPD] 🏁  Quitando marca de hotspot activo..."
rm -f /home/rodo/.hotspot_active

# 9) Reiniciar sistema para aplicar cambios permanentes
echo "[SHPD] 🔁  Reiniciando sistema..."
sudo reboot
