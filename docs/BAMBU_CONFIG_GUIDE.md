# Bambu Lab Printer Configuration Guide

This guide explains how to configure your Bambu Lab printer credentials for use with the `bambu_ams_info.py` tool.

## Configuration Methods

The tool supports **four configuration methods** with the following priority order (highest to lowest):

1. **Command-line arguments** (explicit user intent)
2. **Environment variables** (session/system config)
3. **.env file** (project-level config)
4. **BambuStudio.conf file** (application config)

### Method 1: Command-Line Arguments (Highest Priority)

Pass credentials directly via command-line:

```bash
python pixel_to_3mf\bambu_ams_info.py \
  --ip 192.168.1.100 \
  --access-code 12345678
```

**Pros:**

- Explicit and clear
- Perfect for one-time use or testing
- Overrides all other sources

**Cons:**

- Credentials visible in command history
- Must type each time

### Method 2: Environment Variables

Set environment variables in your shell session:

**PowerShell:**

```powershell
$env:BAMBULAB_PRINTER_IP = "192.168.1.100"
$env:BAMBULAB_ACCESS_CODE = "12345678"
$env:BAMBULAB_SERIAL_NUMBER = "01S00C123456789"  # Optional

python pixel_to_3mf\bambu_ams_info.py
```

**Linux/macOS:**

```bash
export BAMBULAB_PRINTER_IP="192.168.1.100"
export BAMBULAB_ACCESS_CODE="12345678"
export BAMBULAB_SERIAL_NUMBER="01S00C123456789"  # Optional

python pixel_to_3mf/bambu_ams_info.py
```

**Pros:**

- Session-specific
- Can be set in shell profile for persistence
- Not stored in repository

**Cons:**

- Must set each session (unless in profile)
- Not automatically shared with team

### Method 3: .env File (Recommended)

Create a `.env` file in the project root:

1. **Copy the example:**

   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` with your values:**

   ```bash
   BAMBULAB_PRINTER_IP=192.168.1.100
   BAMBULAB_ACCESS_CODE=12345678
   BAMBULAB_SERIAL_NUMBER=01S00C123456789  # Optional
   ```

3. **Run the tool** (credentials loaded automatically):

   ```bash
   python pixel_to_3mf\bambu_ams_info.py
   ```

**Pros:**

- ✅ Convenient - set once, use everywhere
- ✅ Automatically loaded by `python-dotenv`
- ✅ Gitignored by default (secure)
- ✅ Standard practice for project credentials

**Cons:**

- File must be created manually
- Can be accidentally committed if `.gitignore` is wrong (already configured correctly)

### Method 4: BambuStudio.conf File (Lowest Priority)

Load credentials from BambuStudio's configuration file:

```bash
python pixel_to_3mf\bambu_ams_info.py --use-conf
```

**How it works:**

- Reads from BambuStudio's config file location:
  - **Windows:** `%APPDATA%\BambuStudio\BambuStudio.conf`
  - **macOS:** `~/Library/Application Support/BambuStudio/BambuStudio.conf`
  - **Linux:** `~/.config/BambuStudio/BambuStudio.conf`
- Extracts access code for your printer
- If multiple printers, use `--serial-number` to specify which one

**Pros:**

- Uses existing BambuStudio credentials
- No duplicate configuration needed
- Perfect if BambuStudio already configured

**Cons:**

- Requires BambuStudio installation
- Still need to provide IP address separately
- Lowest priority (overridden by everything else)

## Finding Your Credentials

### Access Code

#### Option 1: From Printer Screen (Access Code)

1. Go to printer settings
2. Navigate to Network settings
3. Find "LAN Access Code"

#### Option 2: From BambuStudio (Access Code)

1. Open BambuStudio
2. Go to device settings
3. Look for "Access Code" or use `--use-conf`

### Printer IP Address

#### Option 1: From Printer Screen (IP Address)

1. Go to Network settings
2. Find IPv4 address

#### Option 2: From Router (IP Address)

1. Log into your router admin panel
2. Look for DHCP clients
3. Find device named "Bambu Lab" or similar

#### Option 3: Network Scan

```bash
# Use nmap or similar
nmap -sn 192.168.1.0/24
```

### Serial Number (Optional)

Found on:

- Printer label (physical printer)
- BambuStudio device list
- BambuStudio.conf file

## Usage Examples

### Example 1: Using .env File (Recommended)

```bash
# Create .env file
echo "BAMBULAB_PRINTER_IP=192.168.1.100" > .env
echo "BAMBULAB_ACCESS_CODE=12345678" >> .env

# Run tool
python pixel_to_3mf\bambu_ams_info.py
```

### Example 2: Using BambuStudio.conf

```bash
# Load from conf file, but still need IP
python pixel_to_3mf\bambu_ams_info.py \
  --ip 192.168.1.100 \
  --use-conf
```

### Example 3: Override .env with CLI

```bash
# .env has one printer, but test different one via CLI
python pixel_to_3mf\bambu_ams_info.py \
  --ip 192.168.1.101 \
  --access-code different_code
```

### Example 4: Environment Variable Override

```powershell
# Temporarily override .env file for this session
$env:BAMBULAB_PRINTER_IP = "192.168.1.101"
python pixel_to_3mf\bambu_ams_info.py
```

## Testing Connection

Test your configuration before querying AMS:

```bash
python pixel_to_3mf\bambu_ams_info.py --test-connection
```

This will:

- ✅ Validate credentials work
- ✅ Print raw JSON response
- ✅ Help debug connection issues

## Security Best Practices

1. **Never commit `.env` file** - Already in `.gitignore`
2. **Don't share access codes publicly** - Treat like passwords
3. **Use command-line for temporary testing** - Overrides persist config
4. **Rotate access codes if exposed** - Can be changed in printer settings
5. **Use .env for development** - Project-level secrets

## Troubleshooting

### "Printer IP required" Error

- Check `.env` file exists and has `BAMBULAB_PRINTER_IP`
- Verify environment variable is set
- Or provide via `--ip` argument

### "Access code required" Error

- Check `.env` file exists and has `BAMBULAB_ACCESS_CODE`
- Try `--use-conf` if BambuStudio installed
- Or provide via `--access-code` argument

### "Connection failed" Error

- Verify printer IP is correct (ping it first)
- Check access code is correct
- Ensure printer and computer on same network
- Try `--test-connection` to see raw error

### BambuStudio.conf Not Found

- Verify BambuStudio is installed
- Check file path for your OS
- Use `.env` file instead as fallback

## Priority Demonstration

Given these configurations:

- **.env:** IP=192.168.1.100, CODE=aaaa
- **Environment:** CODE=bbbb
- **CLI:** CODE=cccc

The tool will use:

- **IP:** 192.168.1.100 (from .env, no override)
- **CODE:** cccc (CLI overrides everything)

If CLI removed:

- **CODE:** bbbb (environment overrides .env)

If environment cleared:

- **CODE:** aaaa (falls back to .env)

## Integration with Other Tools

The `get_config_value()` function is reusable for other configuration needs:

```python
from pixel_to_3mf.bambu_ams_info import get_config_value

# Resolve any config value with priority handling
value = get_config_value(
    cli_value=args.my_param,
    env_var_name="MY_ENV_VAR",
    conf_value=conf_dict.get("my_value"),
    default="fallback"
)
```

This ensures consistent configuration behavior across all tools.
