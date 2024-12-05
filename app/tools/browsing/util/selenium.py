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

    # Add required arguments for headless mode
    # Headless mode configuration
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox") 
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    
    # Renderer/GPU configuration
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-gpu-sandbox")
    options.add_argument("--disable-setuid-sandbox")
    options.add_argument("--disable-accelerated-2d-canvas")
    options.add_argument("--disable-accelerated-jpeg-decoding")
    options.add_argument("--disable-accelerated-mjpeg-decode")
    options.add_argument("--disable-accelerated-video-decode")
    options.add_argument("--disable-gpu-compositing")
    
    # Memory/process configuration
    options.add_argument("--single-process")
    options.add_argument("--no-zygote")
    options.add_argument("--disable-infobars")
    
    # Browser security/automation configuration
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-web-security")
    options.add_argument("--allow-running-insecure-content")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    # Error handling configuration
    options.add_argument("--disable-crash-reporter")
    options.add_argument("--disable-in-process-stack-traces")
    options.add_argument("--disable-logging")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--log-level=3")
    options.add_argument("--silent")
    
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
