import pandas as pd
import matplotlib.pyplot as plt

def main():
    # Load CSV log
    df = pd.read_csv("logs/example_latency_laptop.csv")

    # Plot latency vs frame
    plt.figure(figsize=(8, 4))
    plt.plot(df["frame"], df["latency_ms"], linewidth=1)
    plt.xlabel("Frame Index")
    plt.ylabel("Latency (ms)")
    plt.title("ROI Latency per Frame (Laptop Baseline)")
    plt.grid(True)

    # Save figure
    plt.savefig("results/figures/latency_laptop.png", dpi=150)
    plt.close()

if __name__ == "__main__":
    main()
