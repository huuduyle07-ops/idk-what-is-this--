from html.parser import HTMLParser


class FormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inputs = []
        self.labels = []
        self.buttons = []

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == "input":
            self.inputs.append(data)
        elif tag == "label":
            self.labels.append(data)
        elif tag == "button":
            self.buttons.append(data)


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()

    parser = FormParser()
    parser.feed(html)

    inputs_by_name = {
        item.get("name"): item
        for item in parser.inputs
    }

    email = inputs_by_name.get("email")
    password = inputs_by_name.get("password")

    require(email is not None, "email input missing")
    require(password is not None, "password input missing")

    require(email.get("type") == "email", "email input must use type=email")
    require("required" in email, "email input must be required")
    require(email.get("id"), "email input must have id")

    require(password.get("type") == "password", "password input must use type=password")
    require("required" in password, "password input must be required")
    require(password.get("id"), "password input must have id")

    label_targets = {label.get("for") for label in parser.labels}
    require(email.get("id") in label_targets, "email label must target email input id")
    require(password.get("id") in label_targets, "password label must target password input id")

    require(any(button.get("type") == "submit" for button in parser.buttons), "submit button must have type=submit")

    print("OK")


if __name__ == "__main__":
    main()
