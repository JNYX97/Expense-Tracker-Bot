import io
import matplotlib
matplotlib.use("Agg")  # non-interactive backend, safe for servers
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches


# Colour palette: green → yellow → red based on % spent
def _status_colour(pct: float) -> str:
    if pct >= 100:
        return "#e74c3c"   # red
    elif pct >= 80:
        return "#f39c12"   # amber
    else:
        return "#2ecc71"   # green


def generate_alerts_chart(budget_data: list[dict]) -> io.BytesIO:
    """
    budget_data: list of dicts with keys:
        category (str), spent (float), limit (float), cat_type (str)

    Returns a BytesIO PNG image ready to send via Telegram.
    """
    if not budget_data:
        raise ValueError("No budget data to chart")

    # ── Layout: two side-by-side subplots (monthly | annual) ──────────────────
    monthly = [d for d in budget_data if d["cat_type"] == "monthly"]
    annual  = [d for d in budget_data if d["cat_type"] == "annual"]

    has_monthly = bool(monthly)
    has_annual  = bool(annual)
    n_plots     = int(has_monthly) + int(has_annual)

    fig, axes = plt.subplots(1, n_plots, figsize=(6 * n_plots, 6))
    fig.patch.set_facecolor("#1e1e2e")

    if n_plots == 1:
        axes = [axes]

    plot_index = 0

    def _draw_pie(ax, data, title):
        labels  = [d["category"].title() for d in data]
        sizes   = [max(d["spent"], 0.01) for d in data]   # avoid zero-size slices
        colours = [_status_colour((d["spent"] / d["limit"]) * 100) for d in data]

        wedges, texts, autotexts = ax.pie(
            sizes,
            labels=None,
            colors=colours,
            autopct="%1.0f%%",
            startangle=140,
            pctdistance=0.75,
            wedgeprops={"linewidth": 1.5, "edgecolor": "#1e1e2e"},
        )

        for at in autotexts:
            at.set_color("white")
            at.set_fontsize(9)
            at.set_fontweight("bold")

        # Centre label — total spent vs total budget
        total_spent  = sum(d["spent"] for d in data)
        total_budget = sum(d["limit"] for d in data)
        ax.text(0, 0,
                f"${total_spent:.0f}\n/ ${total_budget:.0f}",
                ha="center", va="center",
                fontsize=10, fontweight="bold", color="white")

        ax.set_title(title, color="white", fontsize=13, fontweight="bold", pad=14)
        ax.set_facecolor("#1e1e2e")

        # Legend with spent / limit per category
        legend_labels = [
            f"{d['category'].title()}  ${d['spent']:.2f} / ${d['limit']:.2f}"
            for d in data
        ]
        patches = [
            mpatches.Patch(color=colours[i], label=legend_labels[i])
            for i in range(len(data))
        ]
        ax.legend(
            handles=patches,
            loc="lower center",
            bbox_to_anchor=(0.5, -0.22),
            fontsize=8,
            frameon=False,
            labelcolor="white",
            ncol=1,
        )

    if has_monthly:
        _draw_pie(axes[plot_index], monthly, "🗓 Monthly Budgets")
        plot_index += 1

    if has_annual:
        _draw_pie(axes[plot_index], annual, "📅 Annual Budgets")

    # Colour key at the bottom
    key_patches = [
        mpatches.Patch(color="#2ecc71", label="On track (< 80%)"),
        mpatches.Patch(color="#f39c12", label="Nearing limit (80–99%)"),
        mpatches.Patch(color="#e74c3c", label="Over budget (≥ 100%)"),
    ]
    fig.legend(
        handles=key_patches,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.04),
        ncol=3,
        fontsize=8,
        frameon=False,
        labelcolor="white",
    )

    plt.tight_layout(rect=[0, 0.06, 1, 1])

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150,
                bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf
