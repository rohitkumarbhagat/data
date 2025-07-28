#!/bin/bash

# create_custom_cacert.sh
# Script to create a custom certificate bundle with missing intermediate certificates
# for EPA server SSL verification

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CUSTOM_CERT_FILE="${SCRIPT_DIR}/custom_cacert.pem"
TEMP_INTERMEDIATE_CERT="/tmp/digicert_global_g2_tls_rsa_sha256_2020_ca1.pem"
INTERMEDIATE_CERT_URL="https://cacerts.digicert.com/DigiCertGlobalG2TLSRSASHA2562020CA1-1.crt.pem"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Creating custom certificate bundle for EPA server SSL verification...${NC}"

# Step 1: Find the base certificate bundle
echo -e "${YELLOW}Step 1: Finding base certificate bundle...${NC}"

# Try to find certifi bundle first
if command -v python3 &> /dev/null; then
    BASE_CERT_FILE=$(python3 -c "import certifi; print(certifi.where())" 2>/dev/null || echo "")
    if [[ -f "$BASE_CERT_FILE" ]]; then
        echo "Found certifi bundle: $BASE_CERT_FILE"
    else
        BASE_CERT_FILE=""
    fi
fi

# Fallback to system certificate locations
if [[ -z "$BASE_CERT_FILE" ]]; then
    echo "Certifi not found, checking system certificate locations..."
    
    # Common certificate locations
    CERT_LOCATIONS=(
        "/etc/ssl/cert.pem"                          # macOS
        "/usr/local/etc/openssl/cert.pem"           # macOS Homebrew
        "/etc/ssl/certs/ca-certificates.crt"        # Linux
        "/etc/pki/tls/certs/ca-bundle.crt"         # RHEL/CentOS
    )
    
    for cert_file in "${CERT_LOCATIONS[@]}"; do
        if [[ -f "$cert_file" ]]; then
            BASE_CERT_FILE="$cert_file"
            echo "Found system certificate bundle: $BASE_CERT_FILE"
            break
        fi
    done
fi

if [[ -z "$BASE_CERT_FILE" ]]; then
    echo -e "${RED}Error: No certificate bundle found. Please install certifi or ensure system certificates are available.${NC}"
    exit 1
fi

# Step 2: Download the missing intermediate certificate
echo -e "${YELLOW}Step 2: Downloading missing intermediate certificate...${NC}"

if curl -s -o "$TEMP_INTERMEDIATE_CERT" "$INTERMEDIATE_CERT_URL"; then
    echo "Downloaded intermediate certificate to: $TEMP_INTERMEDIATE_CERT"
else
    echo -e "${RED}Error: Failed to download intermediate certificate from $INTERMEDIATE_CERT_URL${NC}"
    exit 1
fi

# Step 3: Verify the downloaded certificate
echo -e "${YELLOW}Step 3: Verifying downloaded certificate...${NC}"

if openssl x509 -in "$TEMP_INTERMEDIATE_CERT" -text -noout | grep -q "DigiCert Global G2 TLS RSA SHA256 2020 CA1"; then
    echo "Certificate verification successful"
else
    echo -e "${RED}Error: Downloaded certificate is not the expected DigiCert intermediate certificate${NC}"
    rm -f "$TEMP_INTERMEDIATE_CERT"
    exit 1
fi

# Step 4: Create the custom certificate bundle
echo -e "${YELLOW}Step 4: Creating custom certificate bundle...${NC}"

# Copy base certificate bundle
cp "$BASE_CERT_FILE" "$CUSTOM_CERT_FILE"

# Add a separator comment and append the intermediate certificate
{
    echo ""
    echo "# DigiCert Global G2 TLS RSA SHA256 2020 CA1 (added $(date) for EPA server)"
    cat "$TEMP_INTERMEDIATE_CERT"
} >> "$CUSTOM_CERT_FILE"

# Clean up temporary file
rm -f "$TEMP_INTERMEDIATE_CERT"

# Step 5: Verify the custom bundle
echo -e "${YELLOW}Step 5: Verifying custom certificate bundle...${NC}"

if grep -q "DigiCert Global G2 TLS RSA SHA256 2020 CA1" "$CUSTOM_CERT_FILE"; then
    echo "Custom certificate bundle created successfully"
    echo "Location: $CUSTOM_CERT_FILE"
    
    # Count certificates in the bundle
    cert_count=$(grep -c "BEGIN CERTIFICATE" "$CUSTOM_CERT_FILE")
    echo "Total certificates in bundle: $cert_count"
else
    echo -e "${RED}Error: Failed to create custom certificate bundle${NC}"
    exit 1
fi

# Step 6: Test the custom bundle (optional)
echo -e "${YELLOW}Step 6: Testing custom certificate bundle...${NC}"

if command -v python3 &> /dev/null; then
    if python3 -c "
import requests
try:
    response = requests.head('https://gaftp.epa.gov/air/nei/2020/data_summaries/2020neiMar_nonpoint.zip', verify='$CUSTOM_CERT_FILE', timeout=10)
    print('SSL verification test: SUCCESS')
    print(f'Status: {response.status_code}')
except Exception as e:
    print(f'SSL verification test: FAILED - {e}')
    exit(1)
" 2>/dev/null; then
        echo -e "${GREEN}Custom certificate bundle is working correctly!${NC}"
    else
        echo -e "${YELLOW}Warning: Could not test certificate bundle (requests library not available)${NC}"
    fi
else
    echo -e "${YELLOW}Warning: Could not test certificate bundle (python3 not available)${NC}"
fi

echo -e "${GREEN}✅ Custom certificate bundle created successfully!${NC}"
echo -e "${GREEN}📁 Location: $CUSTOM_CERT_FILE${NC}"
echo -e "${GREEN}🔧 Usage: Use this file as the verify parameter in requests.get()${NC}"