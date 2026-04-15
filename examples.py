"""Run this to see all flashbar features in action."""
from flashbar import Bar, track, Spinner
import time


def main():
    print("── track() with themes ─────────────────────\n")
    for item in track(range(40), label="Default ", theme="default"):
        time.sleep(0.02)
    for item in track(range(40), label="Retro   ", theme="retro"):
        time.sleep(0.02)
    for item in track(range(40), label="Slim    ", theme="slim"):
        time.sleep(0.02)
    for item in track(range(40), label="Dots    ", theme="dots"):
        time.sleep(0.02)
    for item in track(range(40), label="Arrow   ", theme="arrow"):
        time.sleep(0.02)

    print("\n── custom colors ───────────────────────────\n")
    for item in track(range(40), label="Hex     ", color="#FF5733"):
        time.sleep(0.02)
    for item in track(range(40), label="Mint    ", color="#00FF99"):
        time.sleep(0.02)

    print("\n── custom characters ───────────────────────\n")
    bar = Bar(40, fill="▓", empty="▒", color="cyan", label="Custom  ")
    for _ in range(40):
        bar.update()
        time.sleep(0.02)

    print("\n── ETA + speed ─────────────────────────────\n")
    bar = Bar(60, label="Speed   ", show_speed=True, theme="green")
    for _ in range(60):
        bar.update()
        time.sleep(0.03)

    print("\n── context manager ─────────────────────────\n")
    with Bar(40, label="Managed ", theme="minimal") as bar:
        for _ in range(40):
            bar.update()
            time.sleep(0.02)

    print("\n── spinner ─────────────────────────────────\n")
    for style in ["dots", "circle", "bounce", "arrows"]:
        with Spinner(f"Spinner ({style})", style=style, color="magenta"):
            time.sleep(1.5)

    print("\nAll done! ⚡")


if __name__ == "__main__":
    main()
