"""COOKING SKILL — recipes, steps, substitutes, kitchen help."""
import webbrowser

_QUE = ("cook", "recipe", "bake", " ingredients", "kitchen", "dinner", "lunch",
        "breakfast", "how do i make", "how to make", "substitute", "how long do i")

_ESSENTIALS = {
    "pasta": ["pasta", "salt", "water", "olive oil", "garlic", "tomato"],
    "rice": ["rice", "water", "salt", "butter"],
    "omelette": ["eggs", "butter", "salt", "pepper", "milk"],
    "pancake": ["flour", "milk", "eggs", "sugar", "baking powder"],
    "chicken": ["chicken", "salt", "pepper", "oil", "garlic"],
    "tea": ["water", "tea leaves", "sugar", "milk"],
    "coffee": ["coffee", "water", "sugar", "milk"],
    "maggie": ["maggie noodles", "water", "tastemaker", "vegetables"],
}


def match(text):
    return any(q in text for q in _QUE)


def reply(text, say, ask):
    dish = None
    for d in _ESSENTIALS:
        if d in text:
            dish = d
            break
    if not dish:
        dish = ask("Which dish should I help with?").lower() or ""
        for d in _ESSENTIALS:
            if d in dish:
                break
        else:
            dish = None
    if not dish:
        say("I don't have that one memorised — searching a recipe online.")
        webbrowser.open(f"https://www.google.com/search?q={text.replace(' ', '+')}+recipe")
        return "Recipe opened in your browser."

    items = _ESSENTIALS[dish]
    return (f"For {dish} you need: {', '.join(items)}. "
            f"Want the step-by-step? Say 'guide me through {dish}'. "
            f"Or say 'cook {dish} with me' and I'll walk you live.")
