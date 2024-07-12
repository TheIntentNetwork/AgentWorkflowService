
def get_b64_screenshot(wd, element=None):
    if element:
        screenshot_b64 = element.screenshot_as_base64
    else:
        try:
            screenshot_b64 = wd.get_screenshot_as_base64()
        except Exception as e:
            screenshot_b64 = wd.get_screenshot_as_png()

    return screenshot_b64