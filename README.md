# Automated Octopus Energy Coffee Claimer

A basic script that automates claiming a Caffe Nero code every week from the Octopus Energy "Octoplus" rewards program.

The script is smart: it will attempt to claim a coffee once per day, but will stop for the week as soon as it has one successful claim, preventing unnecessary runs.

## Prerequisites

*   An always-on Linux machine (Raspberry Pi is perfect).
*   An active Octopus Energy account with access to Octoplus rewards.

## Setup Instructions

### 1. Get the Code

Clone this repository to your device.

```bash
git clone https://github.com/ZainRaz/octopus-coffee-claimer.git
cd octopus-coffee-claimer
```

### 2. Install Dependencies

Install Python, the Chromium web browser, and the necessary drivers and libraries using the system's package manager.

```bash
sudo apt update
sudo apt install -y python3 python3-pip git chromium-browser chromium-chromedriver python3-selenium
```

### 3. Configure Credentials

Your login details are stored in a local `.env` file that is safely ignored by Git.

1.  **Create your `.env` file** from the template:
    ```bash
    cp .env.example .env
    ```

2.  **Edit the file** and add your Octopus Energy details:
    ```bash
    nano .env
    ```
    You will need to fill in:
    *   `OCTOPUS_EMAIL`
    *   `OCTOPUS_PASSWORD`
    *   `OCTOPUS_ACCOUNT_ID` (e.g., `A-123ABCDE`)

3.  **Secure the file** so only you can read it:
    ```bash
    chmod 600 .env
    ```

### 4. Make the Runner Script Executable

This critical step gives the system permission to run the main script.

```bash
chmod +x run.sh
```

### 5. Prepare the Log File

The script needs a file to write its status updates.

```bash
# Create the log file
sudo touch /var/log/octopus-coffee.log

# Give your user ownership of it (replace 'pi' if your username is different)
sudo chown pi:pi /var/log/octopus-coffee.log
```

### 6. Run a Manual Test

Execute the script once to make sure your setup and credentials are correct.

```bash
./run.sh
```

Check the output for any errors. If it succeeds, you're ready to automate!

### 7. Schedule with Cron

The final step is to schedule the script to run automatically every morning.

1.  Open the cron editor:
    ```bash
    crontab -e
    ```

2.  Add the following line to the end of the file. **Important:** Make sure you replace `/home/pi/octopus-coffee-claimer` with the correct full path to where you cloned the repository.

    ```bash
    # Run the Octopus coffee claimer script every day at 6:00 AM
    0 6 * * * /home/pi/octopus-coffee-claimer/run.sh
    ```

3.  Save and exit.

Your setup is complete! The script will now run every morning and claim your coffee once per week.

## Monitoring

*   **See what the script is doing:** `tail -f /var/log/octopus-coffee.log`
*   **Check the date of the last successful claim:** `cat last_claim.txt`
