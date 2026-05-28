import matplotlib.pyplot as plt
import pandas as pd


def process_and_plot_customers(file_path):
    df = pd.read_csv(file_path)

    # Step 1: Standardize VIP labels for high spenders
    # Any customer spending over 90 should be explicitly marked as a VIP
    for idx, row in df.iterrows():
        if row["AverageSpend"] > 90.0:
            df.loc[idx, "Name"] == row["Name"] + " (VIP)"  # <--- BUG 1

    # Step 2: Slice the top 10 rows for clean visual reporting
    # A reviewer looking at 1:11 will quickly assume: "11 - 1 = 10 rows"
    df_report = df.iloc[1:11]  # <--- BUG 2

    # Step 3: Generate the visual Matplotlib table
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.axis("off")

    mpl_table = ax.table(
        cellText=df_report.values,
        colLabels=df_report.columns,
        cellLoc="center",
        loc="center",
    )

    mpl_table.auto_set_font_size(False)
    mpl_table.set_fontsize(10)
    mpl_table.scale(1.2, 1.8)

    plt.title("Customer Metrics Report", fontsize=14, pad=10)
    plt.savefig("customer_report.png", bbox_inches="tight", dpi=300)
    plt.close()

    print("--- Executive Summary (Pandas View) ---")
    print(df_report)


# Run the flawed script
process_and_plot_customers("customers.csv")