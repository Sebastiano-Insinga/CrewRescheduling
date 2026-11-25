#!/usr/bin/env python3
"""Frequency tables, Excel workbook and charts shared by the distribution scripts.

Domain free: classes, labels and titles come from the caller.
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def short_name(path):
    name = os.path.basename(path)[: -len(".csv")]
    for prefix in ("Transformed-", "manuel-"):
        if name.startswith(prefix):
            name = name[len(prefix):]
    for suffix in ("-disrupted_1", "-disrupted"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    if len(name) > 31:
        sys.exit(f"[error] instance label '{name}' is longer than 31 characters, "
                 f"excel sheets cannot be named after it")
    return name


def class_table(df, labels):
    total = len(df)
    counts = df["class"].value_counts().reindex(labels, fill_value=0)
    return pd.DataFrame({
        "class": labels,
        "count": counts.values,
        "share_pct": counts.values / total * 100.0,
    })


def check(name, df, classes):
    total = int(classes["count"].sum())
    if total != len(df):
        sys.exit(f"[error] {name}: class counts sum to {total}, csv has {len(df)} rows")
    share = classes["share_pct"].sum()
    if abs(share - 100.0) > 1e-6:
        sys.exit(f"[error] {name}: shares sum to {share}, not to 100")


def drop_empty_classes(df, labels):
    empty = [label for label in labels if label in df.columns and df[label].sum() == 0]
    return df.drop(columns=empty)


def all_instances_row(total_counts, labels):
    total = sum(total_counts.values())
    row = {"instance": "All instances", "duties": total}
    row.update({label: total_counts[label] / total * 100.0 for label in labels})
    return row


def draw_stacked(shares, total_counts, labels, legend_labels, png_path, pdf_path,
                 title, legend_title, xlabel="Share of duties (%)", colormap="YlOrRd",
                 last_class_grey=False):
    to_draw = pd.concat([shares, pd.DataFrame([all_instances_row(total_counts, labels)])],
                        ignore_index=True)
    y_labels = [f"{name} (n={duties})" for name, duties
                in zip(to_draw["instance"], to_draw["duties"])]

    coloured = labels[:-1] if last_class_grey else labels
    colors = plt.get_cmap(colormap)([i / (len(coloured) - 1) * 0.85 + 0.1
                                     for i in range(len(coloured))])
    colors = list(colors) + (["#9e9e9e"] if last_class_grey else [])

    fig, ax = plt.subplots(figsize=(11, 0.42 * len(y_labels) + 3.0))
    left = pd.Series(0.0, index=to_draw.index)
    for label, color in zip(labels, colors):
        values = to_draw[label]
        if values.sum() > 0:
            ax.barh(y_labels, values, left=left,
                    color=color, edgecolor="white", linewidth=0.5,
                    label=legend_labels[label])
        left = left + values

    ax.set_ylim(-0.6, len(y_labels) - 0.4)
    ax.set_xlim(0, 100)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Instance (ordered by number of duties)")
    ax.set_title(title, fontsize=13, pad=14)
    ax.legend(title=legend_title, bbox_to_anchor=(1.01, 1.0), loc="upper left",
              frameon=False)
    ax.grid(axis="x", linestyle=":", alpha=0.5)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(png_path, dpi=300)
    fig.savefig(pdf_path)
    plt.close(fig)


def draw_table(shares, legend_labels, png_path, pdf_path, title, drop_columns=(),
               strip_from_header=""):
    shares = shares.drop(columns=list(drop_columns), errors="ignore")
    header = ["Instance", "Duties"]
    for column in shares.columns[2:]:
        label = legend_labels[column]
        if strip_from_header:
            label = label.replace(strip_from_header, "")
        header.append(label)
    body = [[str(row[0]), str(row[1])] + [f"{v:.1f}%" for v in row[2:]]
            for row in shares.itertuples(index=False)]

    fig, ax = plt.subplots(figsize=(0.95 * len(header) + 2.0, 0.19 * len(body) + 1.2))
    ax.axis("off")
    ax.set_title(title, fontsize=12, pad=12)
    table = ax.table(cellText=body, colLabels=header, loc="upper center", cellLoc="right")
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.auto_set_column_width(list(range(len(header))))
    table.scale(1, 1.3)

    for (row, column), cell in table.get_celld().items():
        cell.set_edgecolor("#d0d0d0")
        if row == 0:
            cell.set_text_props(weight="bold")
            cell.set_facecolor("#f0f0f0")
        elif row == len(body):
            cell.set_text_props(weight="bold")
            cell.set_facecolor("#f7f7f7")
        if column == 0:
            cell.set_text_props(ha="left")

    fig.tight_layout()
    fig.savefig(png_path, dpi=300, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    plt.close(fig)


def write_report(csv_files, out_dir, labels, legend_labels, read_instance, summary_row,
                 xlsx_name, chart_name, chart_title, legend_title,
                 table_title, per_instance_check=None, table_drop_columns=(),
                 strip_from_header="", colormap="YlOrRd", last_class_grey=False):
    per_instance, summary, share_rows, count_rows = {}, [], [], []
    total_counts = dict.fromkeys(labels, 0)

    for path in csv_files:
        name = short_name(path)
        df = read_instance(path)
        if per_instance_check is not None:
            per_instance_check(name, df)
        classes = class_table(df, labels)
        check(name, df, classes)

        per_instance[name] = classes
        summary.append(summary_row(name, df))
        share_rows.append({"instance": name, "duties": len(df),
                           **dict(zip(classes["class"], classes["share_pct"]))})
        count_rows.append({"instance": name, "duties": len(df),
                           **dict(zip(classes["class"], classes["count"]))})
        for label, how_many in zip(classes["class"], classes["count"]):
            total_counts[label] += int(how_many)
        classes.round({"share_pct": 1}).to_csv(
            os.path.join(out_dir, f"classes_{name}.csv"), index=False)

    summary = pd.DataFrame(summary).sort_values("duties").reset_index(drop=True)
    shares = pd.DataFrame(share_rows).sort_values("duties").reset_index(drop=True)
    counts = pd.DataFrame(count_rows).sort_values("duties").reset_index(drop=True)

    shares_with_total = drop_empty_classes(pd.concat(
        [shares, pd.DataFrame([all_instances_row(total_counts, labels)])],
        ignore_index=True).round(1), labels)
    counts = drop_empty_classes(counts, labels)

    summary.to_csv(os.path.join(out_dir, "summary_by_instance.csv"), index=False)
    shares_with_total.to_csv(os.path.join(out_dir, "shares_by_class.csv"), index=False)
    counts.to_csv(os.path.join(out_dir, "counts_by_class.csv"), index=False)

    xlsx_path = os.path.join(out_dir, xlsx_name)
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        shares_with_total.to_excel(writer, sheet_name="shares", index=False)
        counts.to_excel(writer, sheet_name="counts", index=False)
        summary.to_excel(writer, sheet_name="summary", index=False)
        for name, classes in per_instance.items():
            classes.round({"share_pct": 1}).to_excel(writer, sheet_name=name, index=False)
            summary[summary["instance"] == name].to_excel(
                writer, sheet_name=name, index=False, startrow=len(classes) + 2)

    png_path = os.path.join(out_dir, chart_name + ".png")
    pdf_path = os.path.join(out_dir, chart_name + ".pdf")
    draw_stacked(shares, total_counts, labels, legend_labels, png_path, pdf_path,
                 chart_title, legend_title, colormap=colormap,
                 last_class_grey=last_class_grey)

    table_png = os.path.join(out_dir, "shares_by_class.png")
    table_pdf = os.path.join(out_dir, "shares_by_class.pdf")
    draw_table(shares_with_total, legend_labels, table_png, table_pdf, table_title,
               drop_columns=table_drop_columns, strip_from_header=strip_from_header)

    with pd.option_context("display.width", 200, "display.max_columns", 50):
        print(shares_with_total.round(2).to_string(index=False))
    print(f"\ncheck: {len(csv_files)} instances, counts and shares consistent")
    for path in (xlsx_path, os.path.join(out_dir, "shares_by_class.csv"),
                 os.path.join(out_dir, "counts_by_class.csv"),
                 os.path.join(out_dir, "summary_by_instance.csv"),
                 png_path, pdf_path, table_png, table_pdf):
        print(f"  {path}")
