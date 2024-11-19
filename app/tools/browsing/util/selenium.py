import os

wd = None

selenium_config = {
    "chrome_profile_path": None,
    "headless": True,  # Changed to True since we're using headless mode
    "full_page_screenshot": True,
}


def get_web_driver():
    print("Initializing WebDriver...")
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        print("Selenium imported successfully.")
    except ImportError:
        print("Selenium not installed. Please install it with pip install selenium")
        raise ImportError

    try:
        from webdriver_manager.chrome import ChromeDriverManager
        print("webdriver_manager imported successfully.")
    except ImportError:
        print("webdriver_manager not installed. Please install it with pip install webdriver-manager")
        raise ImportError

    try:
        from selenium_stealth import stealth
        print("selenium_stealth imported successfully.")
    except ImportError:
        print("selenium_stealth not installed. Please install it with pip install selenium-stealth")
        raise ImportError

    global wd, selenium_config

    if wd:
        print("Returning existing WebDriver instance.")
        return wd

    # Initialize ChromeDriver service
    service = Service(ChromeDriverManager().install())
    print("ChromeDriver service initialized.")

    # Configure Chrome options
    options = webdriver.ChromeOptions()
    print("ChromeOptions initialized.")

    # Add required arguments
    options.add_argument("--disable-extensions")
    options.add_argument("--headless")
    options.add_argument("--no-sandbox") 
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--enable-gpu")

    if selenium_config.get("headless", False):
        #chrome_options.add_argument('--headless')
        print("Headless mode enabled.")
    if selenium_config.get("full_page_screenshot", False):
        options.add_argument("--start-maximized")
        print("Full page screenshot mode enabled.")
    else:
        options.add_argument("--window-size=1920,1080")
        print("Window size set to 1920,1080.")
    
    # Configure preferences
    prefs = {
        "profile.default_content_settings": {"images": 2}
    }
    options.add_experimental_option("prefs", prefs)

    # Add additional required options
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-web-security")
    options.add_argument("--allow-running-insecure-content")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # Handle profile settings if specified
    chrome_profile_path = selenium_config.get("chrome_profile_path", None)
    if isinstance(chrome_profile_path, str) and os.path.exists(chrome_profile_path):
        profile_directory = os.path.split(chrome_profile_path)[-1].strip("\\").rstrip("/")
        user_data_dir = os.path.split(chrome_profile_path)[0].strip("\\").rstrip("/")
        options.add_argument(f"user-data-dir={user_data_dir}")
        options.add_argument(f"profile-directory={profile_directory}")
        print(f"Using Chrome profile: {profile_directory}")

    try:
        wd = webdriver.Chrome(service=service, options=options)
        print("WebDriver initialized successfully.")
    except Exception as e:
        print(f"Error initializing WebDriver: {e}")
        raise e

    if not selenium_config.get("chrome_profile_path", None):
        stealth(
            wd,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
        )
        print("Stealth mode configured.")

    wd.implicitly_wait(3)
    print("Implicit wait set to 3 seconds.")

    return wd


def set_web_driver(new_wd):
    # remove all popups
    js_script = """
    var popUpSelectors = ['modal', 'popup', 'overlay', 'dialog']; // Add more selectors that are commonly used for pop-ups
    popUpSelectors.forEach(function(selector) {
        var elements = document.querySelectorAll(selector);
        elements.forEach(function(element) {
            // You can choose to hide or remove; here we're removing the element
            element.parentNode.removeChild(element);
        });
    });
    """

    new_wd.execute_script(js_script)

    # Close LinkedIn specific popups
    if "linkedin.com" in new_wd.current_url:
        linkedin_js_script = """
        var linkedinSelectors = ['div.msg-overlay-list-bubble', 'div.ml4.msg-overlay-list-bubble__tablet-height'];
        linkedinSelectors.forEach(function(selector) {
            var elements = document.querySelectorAll(selector);
            elements.forEach(function(element) {
                element.parentNode.removeChild(element);
            });
        });
        """
        new_wd.execute_script(linkedin_js_script)

    new_wd.execute_script("document.body.style.zoom='1.2'")

    global wd
    wd = new_wd


def set_selenium_config(config):
    global selenium_config
    selenium_config = config