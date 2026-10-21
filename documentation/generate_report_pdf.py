from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


OUTPUT_PATH = Path(__file__).with_name("Project_Report.pdf")


def paragraph(text, style):
    return Paragraph(text.replace("&", "&amp;"), style)


def add_table(story, rows, widths=None):
    header_style = ParagraphStyle(
        name="TableHeader",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=10,
        textColor=colors.HexColor("#172033"),
    )
    cell_style = ParagraphStyle(
        name="TableCell",
        fontName="Helvetica",
        fontSize=8.2,
        leading=10,
    )
    wrapped_rows = []
    for row_index, row in enumerate(rows):
        style = header_style if row_index == 0 else cell_style
        wrapped_rows.append([Paragraph(str(cell).replace("&", "&amp;"), style) for cell in row])

    table = Table(wrapped_rows, colWidths=widths, hAlign="LEFT", repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef7")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#172033")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#b8c3d3")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 0.16 * inch))


def build_pdf():
    doc = SimpleDocTemplate(
        str(OUTPUT_PATH),
        pagesize=letter,
        rightMargin=0.7 * inch,
        leftMargin=0.7 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
        title="Product Inventory Management System",
    )

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="SectionHeading",
            parent=styles["Heading2"],
            textColor=colors.HexColor("#17324d"),
            spaceBefore=12,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Body",
            parent=styles["BodyText"],
            leading=14,
            spaceAfter=7,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Small",
            parent=styles["BodyText"],
            fontSize=9,
            leading=12,
            spaceAfter=5,
        )
    )

    story = []
    story.append(Paragraph("Product Inventory Management System", styles["Title"]))
    story.append(Spacer(1, 0.15 * inch))
    story.append(paragraph("Subject: IM102 CRUD Operations Project", styles["Body"]))
    story.append(paragraph("Group Members: Member 1, Member 2, Member 3, Member 4", styles["Body"]))
    story.append(paragraph("Instructor: Instructor Name", styles["Body"]))
    story.append(paragraph("Date: October 8, 2026", styles["Body"]))
    story.append(PageBreak())

    sections = [
        (
            "1. Introduction",
            [
                "The Product Inventory Management System is a desktop application that helps users record and manage product information.",
                "The system uses a graphical interface for CRUD operations and stores records in SQLite so data remains available after reopening the program.",
            ],
        ),
        (
            "2. Project Objectives",
            [
                "General Objective: To develop a simple inventory system that demonstrates complete CRUD operations using Python, Tkinter, and SQLite.",
                "Specific Objectives: create a product entry form, save records, display records in a table, update selected records, delete selected records, calculate dashboard totals, and validate invalid input.",
            ],
        ),
        (
            "3. Functional Requirements",
            [
                "The system must add, view, update, and delete products. It must clear fields, refresh dashboard totals, and display pop-up messages for success, confirmation, validation, and database errors.",
            ],
        ),
    ]

    for title, paragraphs in sections:
        story.append(Paragraph(title, styles["SectionHeading"]))
        for text in paragraphs:
            story.append(paragraph(text, styles["Body"]))

    story.append(Paragraph("4. Tools and Technologies", styles["SectionHeading"]))
    add_table(
        story,
        [
            ["Component", "Tool", "Purpose"],
            ["Programming Language", "Python", "Application logic"],
            ["GUI Library", "Tkinter", "Windows, forms, buttons, and pop-ups"],
            ["Table Widget", "ttk.Treeview", "Display inventory records"],
            ["Database", "SQLite", "Save product information"],
            ["Development Tool", "VS Code or IDLE", "Write and run the program"],
        ],
        [1.7 * inch, 1.5 * inch, 3.2 * inch],
    )

    story.append(Paragraph("5. Data Design", styles["SectionHeading"]))
    story.append(paragraph("The database uses one table named products.", styles["Body"]))
    add_table(
        story,
        [
            ["Column", "Data Type", "Constraint"],
            ["product_id", "INTEGER", "Primary Key, Auto Increment"],
            ["product_name", "TEXT", "Required"],
            ["category", "TEXT", "Required"],
            ["quantity", "INTEGER", "Nonnegative"],
            ["unit_price", "REAL", "Nonnegative"],
        ],
        [1.6 * inch, 1.2 * inch, 3.6 * inch],
    )

    story.append(Paragraph("6. File Design", styles["SectionHeading"]))
    add_table(
        story,
        [
            ["File or Folder", "Purpose"],
            ["main.py", "Contains the Tkinter interface and event handlers"],
            ["database.py", "Contains SQLite setup and CRUD functions"],
            ["inventory.db", "Stores product records and is generated automatically"],
            ["documentation/flowchart.mmd", "Contains the system flowchart"],
            ["screenshots/", "Stores screenshot evidence for testing"],
        ],
        [2.2 * inch, 4.2 * inch],
    )

    story.append(Paragraph("7. Flowchart and Algorithm", styles["SectionHeading"]))
    story.append(paragraph("Process: Start -> Load Database -> Display Products and Totals -> Select Operation -> Validate or Confirm -> Save Changes -> Refresh Table and Totals -> Show Message.", styles["Body"]))
    for heading, steps in [
        ("Add Product Algorithm", ["Enter product details.", "Validate required fields, quantity, and price.", "Insert valid product into SQLite.", "Refresh table and totals.", "Show success message."]),
        ("Read Product Algorithm", ["Open SQLite database.", "Retrieve product records.", "Display records in the table.", "Calculate dashboard totals."]),
        ("Update Product Algorithm", ["Select a product.", "Edit product details.", "Validate new values.", "Update selected record in SQLite.", "Refresh table and totals."]),
        ("Delete Product Algorithm", ["Select a product.", "Ask for confirmation.", "Delete confirmed record.", "Refresh table and totals.", "Show success message."]),
    ]:
        story.append(Paragraph(heading, styles["Heading3"]))
        for index, step in enumerate(steps, 1):
            story.append(paragraph(f"{index}. {step}", styles["Body"]))

    story.append(Paragraph("8. Exception Handling Plan", styles["SectionHeading"]))
    add_table(
        story,
        [
            ["Error Condition", "Expected Pop-up Message"],
            ["Empty product name", "Please enter a product name."],
            ["Quantity contains letters", "Quantity must be a whole number."],
            ["Negative quantity", "Quantity cannot be negative."],
            ["Invalid price", "Please enter a valid price."],
            ["Update without selecting", "Please select a product to update."],
            ["Delete without selecting", "Please select a product to delete."],
            ["Delete confirmation", "Are you sure you want to delete this product?"],
            ["Database error", "Unable to save changes. Please try again."],
        ],
        [2.7 * inch, 3.7 * inch],
    )

    story.append(Paragraph("9. Testing Evidence", styles["SectionHeading"]))
    add_table(
        story,
        [
            ["Test ID", "Test Condition", "Expected Output", "Actual Output", "Remarks"],
            ["TC01", "Add a valid product", "Product added and displayed", "To be recorded", "Pending"],
            ["TC02", "Enter letters as quantity", "Error pop-up displayed", "To be recorded", "Pending"],
            ["TC03", "Enter negative stock", "Input rejected", "To be recorded", "Pending"],
            ["TC04", "Update product stock", "New quantity displayed", "To be recorded", "Pending"],
            ["TC05", "Delete selected product", "Product removed after confirmation", "To be recorded", "Pending"],
            ["TC06", "Cancel deletion", "Product remains unchanged", "To be recorded", "Pending"],
            ["TC07", "Close and reopen program", "Saved changes remain", "To be recorded", "Pending"],
            ["TC08", "Add or delete product", "Dashboard totals recalculate", "To be recorded", "Pending"],
        ],
        [0.6 * inch, 1.45 * inch, 1.65 * inch, 1.35 * inch, 1.0 * inch],
    )

    story.append(Paragraph("10. Conclusion and Recommendations", styles["SectionHeading"]))
    story.append(paragraph("The project demonstrates GUI development with Tkinter, CRUD implementation, SQLite persistence, input validation, and error handling.", styles["Body"]))
    story.append(paragraph("Future improvements may include product search, low-stock alerts, inventory reports, authentication, CSV export, and printable reports.", styles["Body"]))

    story.append(Paragraph("11. Individual Contributions", styles["SectionHeading"]))
    add_table(
        story,
        [
            ["Member", "Contribution"],
            ["Member 1", "GUI design and Tkinter implementation"],
            ["Member 2", "Database design and CRUD functions"],
            ["Member 3", "Input validation, testing, and error handling"],
            ["Member 4", "Flowchart, screenshots, and documentation"],
        ],
        [1.3 * inch, 5.1 * inch],
    )

    story.append(Paragraph("12. Project Summary", styles["SectionHeading"]))
    story.append(paragraph("The Product Inventory Management System is a simple desktop CRUD application for managing product records. It focuses on one product table, complete CRUD operations, validation, automatic dashboard totals, and organized documentation.", styles["Body"]))

    doc.build(story)


if __name__ == "__main__":
    build_pdf()
