import io
import json
import os
import smtplib
from datetime import datetime
from email.message import EmailMessage

from flask import Blueprint, current_app, jsonify, request, send_file
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import HRFlowable, Image as RLImage, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from extensions import csrf
from services.products import load_products
from services.sales import load_sales

receipts_bp = Blueprint("receipts", __name__)

LOGO_PATH = os.path.join("static", "images/logo.png")
LOGO_CID = "receipt_logo"

# TODO: move to environment variables before adding real data
RECEIPT_EMAIL_ADDRESS = "unitbaggy3@gmail.com"
RECEIPT_EMAIL_PASSWORD = "pdzy fphw zjkg zxoh"


def _receipt_file_path(sales_id):
    return f"receipts/{sales_id}.json"


@receipts_bp.route("/api/receipt/generate", methods=["POST"])
@csrf.exempt
def generate_receipt():
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "message": "No data provided"}), 400

        sales_id = data.get("sales_id")
        if not sales_id:
            return jsonify({"success": False, "message": "Sales ID required"}), 400

        sale = None
        for s in load_sales():
            if s.get("sales_id") == sales_id:
                sale = s
                break

        if not sale:
            return jsonify({"success": False, "message": f"Sale {sales_id} not found"}), 404

        items = sale.get("items", [])

        if not items:
            cart = sale.get("cart", [])
            products = load_products()
            for cart_item in cart:
                product_id = cart_item.get("product_id")
                quantity = cart_item.get("quantity", 1)
                for product in products:
                    if str(product.get("barcode")) == str(product_id):
                        items.append({
                            "name": product.get("name", "Unknown"),
                            "quantity": quantity,
                            "price": product.get("price", 0),
                        })
                        break

        receipt_data = {
            "ticket_number": sale.get("sales_id", "N/A"),
            "date": sale.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "served_by": sale.get("served_by", "Eddy"),
            "business_name": "EDMA ELECTRICALS",
            "phone": "0705470644",
            "location": "Nairobi",
            "items": items,
            "subtotal": float(sale.get("total", 0)),
            "tax": 0,
            "total": float(sale.get("total", 0)),
            "payment_method": sale.get("payment_method", "Cash"),
            "amount_paid": float(sale.get("amount_paid", sale.get("total", 0))),
            "change": float(sale.get("change", 0)),
            "customer_name": sale.get("customer_name", ""),
            "customer_email": sale.get("customer_email", ""),
            "customer_phone": sale.get("customer_phone", ""),
            "company": "Pinchezmedia",
            "email": "juliuskyuma24@gmail.com",
            "thank_you": "Thank You For Shopping With Us",
            "policy": "GOODS ARE NOT RETURNABLE AFTER SALE",
            "powered_by": "System by Pinchezmedia254",
        }

        os.makedirs("receipts", exist_ok=True)
        with open(_receipt_file_path(sales_id), "w") as f:
            json.dump(receipt_data, f, indent=2)

        return jsonify({
            "success": True,
            "message": "Receipt generated successfully",
            "receipt_data": receipt_data,
        })

    except Exception as e:
        print(f"Error generating receipt: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500


def build_receipt_pdf(data):
    """Build the receipt PDF from receipt data and return it as a BytesIO buffer.

    Styled to look like a real printed till receipt: narrow strip, monospace
    font, dashed rules. Shared by the download endpoint and the email
    endpoint so both produce the exact same PDF.
    """

    def money(v):
        return f"{float(v):,.2f}"

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
        leftMargin=2 * inch, rightMargin=2 * inch,
    )
    story = []

    brand_style = ParagraphStyle(
        "Brand", fontName="Courier-Bold", fontSize=13,
        alignment=TA_CENTER, spaceAfter=2, textColor=colors.HexColor("#001846"),
    )
    center_style = ParagraphStyle(
        "Center", fontName="Courier", fontSize=8.5,
        alignment=TA_CENTER, spaceAfter=2, textColor=colors.black,
    )
    label_style = ParagraphStyle(
        "Label", fontName="Courier-Bold", fontSize=9,
        alignment=TA_CENTER, spaceBefore=2, spaceAfter=2, textColor=colors.black,
    )
    line_style = ParagraphStyle(
        "Line", fontName="Courier", fontSize=8.5,
        alignment=TA_LEFT, spaceAfter=1, textColor=colors.black,
    )
    right_style = ParagraphStyle(
        "Right", fontName="Courier", fontSize=8.5,
        alignment=TA_RIGHT, spaceAfter=1, textColor=colors.black,
    )
    total_style = ParagraphStyle(
        "Total", fontName="Courier-Bold", fontSize=11,
        alignment=TA_RIGHT, spaceBefore=3, spaceAfter=1, textColor=colors.HexColor("#001846"),
    )
    thanks_style = ParagraphStyle(
        "Thanks", fontName="Courier-Bold", fontSize=10,
        alignment=TA_CENTER, spaceBefore=4, spaceAfter=4, textColor=colors.HexColor("#001846"),
    )
    small_style = ParagraphStyle(
        "Small", fontName="Courier", fontSize=7.5,
        alignment=TA_CENTER, spaceAfter=2, textColor=colors.HexColor("#555555"),
    )
    faint_style = ParagraphStyle(
        "Faint", fontName="Courier", fontSize=7,
        alignment=TA_CENTER, spaceBefore=6, textColor=colors.HexColor("#999999"),
    )

    dash = lambda: story.append(HRFlowable(
        width="100%", thickness=0.75, dash=(2, 2),
        color=colors.HexColor("#999999"), spaceBefore=4, spaceAfter=4,
    ))
    solid = lambda: story.append(HRFlowable(
        width="100%", thickness=1, color=colors.black, spaceBefore=2, spaceAfter=4,
    ))

    logo_shown = False
    if os.path.exists(LOGO_PATH):
        try:
            logo = RLImage(LOGO_PATH)
            target_w = 1.5 * inch
            aspect = logo.imageHeight / float(logo.imageWidth)
            logo.drawWidth = target_w
            logo.drawHeight = target_w * aspect
            logo.hAlign = "CENTER"
            story.append(logo)
            story.append(Spacer(1, 4))
            logo_shown = True
        except Exception:
            logo_shown = False
    if not logo_shown:
        story.append(Paragraph(data["business_name"], brand_style))
    story.append(Paragraph(f"Tel: {data['phone']}", center_style))
    story.append(Paragraph(data["location"], center_style))
    dash()
    story.append(Paragraph("SALES RECEIPT", label_style))
    dash()

    story.append(Paragraph(f"Receipt No : {data['ticket_number']}", line_style))
    story.append(Paragraph(f"Date       : {data['date']}", line_style))
    story.append(Paragraph(f"Served By  : {data['served_by']}", line_style))
    if data.get("customer_name"):
        story.append(Paragraph(f"Customer   : {data['customer_name']}", line_style))
    dash()

    table_data = [["ITEM", "QTY", "AMOUNT"]]
    for item in data["items"]:
        name = item.get("name", "Unknown")
        qty = item.get("quantity", 1)
        price = float(item.get("price", 0))
        total = price * qty
        table_data.append([name[:32], str(qty), money(total)])

    table = Table(table_data, colWidths=[2.5 * inch, 0.5 * inch, 1.2 * inch])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Courier-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Courier"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.75, colors.black),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(table)
    dash()

    story.append(Paragraph(f"Subtotal:  {money(data['subtotal'])} KSh", right_style))
    story.append(Paragraph(f"Tax:       {money(data.get('tax', 0))} KSh", right_style))
    story.append(Paragraph(f"TOTAL:     {money(data['total'])} KSh", total_style))
    solid()
    story.append(Paragraph(f"{data['payment_method'].upper()} PAID: {money(data['amount_paid'])} KSh", right_style))
    if float(data.get("change", 0)) > 0:
        story.append(Paragraph(f"CHANGE DUE: {money(data['change'])} KSh", right_style))
    dash()

    if data.get("company"):
        story.append(Paragraph(data["company"], center_style))
    if data.get("email"):
        story.append(Paragraph(data["email"], center_style))
    story.append(Paragraph(data["thank_you"], thanks_style))
    story.append(Paragraph(data["policy"], small_style))
    story.append(Paragraph(data["powered_by"], faint_style))
    story.append(Paragraph("*** END OF RECEIPT ***", faint_style))

    doc.build(story)
    buffer.seek(0)
    return buffer


@receipts_bp.route("/api/receipt/download/<sales_id>", methods=["GET"])
@csrf.exempt
def download_receipt_pdf(sales_id):
    try:
        receipt_file = _receipt_file_path(sales_id)
        if not os.path.exists(receipt_file):
            return jsonify({
                "success": False,
                "message": "Receipt not found. Please generate receipt first.",
            }), 404

        with open(receipt_file, "r") as f:
            data = json.load(f)

        buffer = build_receipt_pdf(data)
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"receipt_{sales_id}.pdf",
            mimetype="application/pdf",
        )

    except Exception as e:
        print(f"Error downloading receipt: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500


def generate_receipt_html(data):
    def money(v):
        return f"{float(v):,.2f}"

    items_html = ""
    for item in data["items"]:
        name = item.get("name", "Unknown")
        qty = item.get("quantity", 1)
        price = float(item.get("price", 0))
        total = price * qty
        items_html += f"""
            <tr>
                <td>{name}</td>
                <td style="text-align:center;">{qty}</td>
                <td style="text-align:right;">{money(total)}</td>
            </tr>
        """

    customer_info = ""
    if data.get("customer_name"):
        customer_info += f"<div>Customer : {data['customer_name']}</div>"
    if data.get("customer_phone"):
        customer_info += f"<div>Phone    : {data['customer_phone']}</div>"
    if data.get("customer_email"):
        customer_info += f"<div>Email    : {data['customer_email']}</div>"

    change_row = ""
    if float(data.get("change", 0)) > 0:
        change_row = f'<div class="change-row">CHANGE DUE: {money(data["change"])} KSh</div>'

    logo_html = ""
    if os.path.exists(LOGO_PATH):
        logo_html = (
            f'<img src="cid:{LOGO_CID}" alt="{data["business_name"]}" '
            f'style="width:120px; height:auto; display:block; margin:0 auto 4px;">'
        )
    business_header = logo_html if logo_html else f'<div class="business">{data["business_name"]}</div>'

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Receipt {data['ticket_number']}</title>
        <style>
            body {{ font-family: 'Courier New', Courier, monospace; margin: 0; padding: 20px; background: #eceff1; }}
            .receipt {{ max-width: 340px; margin: 0 auto; background: white; padding: 24px 22px; border: 1px solid #ddd; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }}
            .header {{ text-align: center; margin-bottom: 6px; }}
            .business {{ font-size: 19px; font-weight: bold; color: #001846; letter-spacing: 0.5px; }}
            .info {{ text-align: center; font-size: 12px; color: #333; margin: 1px 0; }}
            .dashed {{ border-top: 1px dashed #999; margin: 10px 0; }}
            .solid {{ border-top: 1.5px solid #000; margin: 6px 0; }}
            .label {{ text-align: center; font-weight: bold; font-size: 12px; letter-spacing: 1px; margin: 4px 0; }}
            .ticket-info div {{ font-size: 12px; margin: 1px 0; }}
            .customer-info {{ font-size: 12px; margin: 6px 0; }}
            table {{ width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 12px; }}
            th {{ border-bottom: 1px solid #000; padding: 4px 2px; text-align: left; font-size: 11px; }}
            td {{ padding: 3px 2px; font-size: 12px; }}
            .totals {{ text-align: right; font-size: 12px; margin-top: 4px; }}
            .totals div {{ padding: 1px 0; }}
            .total-row {{ font-size: 15px; font-weight: bold; color: #001846; }}
            .paid-row {{ font-size: 12px; margin-top: 4px; }}
            .change-row {{ font-size: 12px; font-weight: bold; }}
            .footer {{ text-align: center; margin-top: 10px; }}
            .thank-you {{ font-size: 13px; font-weight: bold; color: #001846; margin: 6px 0; }}
            .policy {{ font-size: 10.5px; color: #555; margin-top: 4px; }}
            .powered {{ font-size: 9px; color: #999; margin-top: 8px; }}
            .end-marker {{ font-size: 9px; color: #999; margin-top: 4px; letter-spacing: 1px; }}
        </style>
    </head>
    <body>
        <div class="receipt">
            <div class="header">
                {business_header}
                <div class="info">Tel: {data['phone']}</div>
                <div class="info">{data['location']}</div>
            </div>

            <div class="dashed"></div>
            <div class="label">SALES RECEIPT</div>
            <div class="dashed"></div>

            <div class="ticket-info">
                <div>Receipt No : {data['ticket_number']}</div>
                <div>Date       : {data['date']}</div>
                <div>Served By  : {data['served_by']}</div>
            </div>

            {f'<div class="customer-info">{customer_info}</div>' if customer_info else ''}

            <div class="dashed"></div>

            <table>
                <thead>
                    <tr>
                        <th>ITEM</th>
                        <th style="text-align:center;">QTY</th>
                        <th style="text-align:right;">AMOUNT</th>
                    </tr>
                </thead>
                <tbody>
                    {items_html}
                </tbody>
            </table>

            <div class="dashed"></div>

            <div class="totals">
                <div>Subtotal: {money(data['subtotal'])} KSh</div>
                <div>Tax: {money(data.get('tax', 0))} KSh</div>
                <div class="total-row">TOTAL: {money(data['total'])} KSh</div>
            </div>

            <div class="solid"></div>
            <div class="paid-row">{data['payment_method'].upper()} PAID: {money(data['amount_paid'])} KSh</div>
            {change_row}

            <div class="dashed"></div>

            <div class="footer">
                {f"<div class='info'>{data['company']}</div>" if data.get('company') else ''}
                {f"<div class='info'>{data['email']}</div>" if data.get('email') else ''}
                <div class="thank-you">{data['thank_you']}</div>
                <div class="policy">{data['policy']}</div>
                <div class="powered">{data['powered_by']}</div>
                <div class="end-marker">*** END OF RECEIPT ***</div>
            </div>
        </div>
    </body>
    </html>
    """
    return html


@receipts_bp.route("/api/receipt/email", methods=["POST"])
@csrf.exempt
def send_receipt_email():
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "message": "No data provided"}), 400

        sales_id = data.get("sales_id")
        email = data.get("email")

        if not sales_id:
            return jsonify({"success": False, "message": "Sales ID required"}), 400
        if not email:
            return jsonify({"success": False, "message": "Email address required"}), 400
        if "@" not in email or "." not in email:
            return jsonify({"success": False, "message": "Invalid email address"}), 400

        receipt_file = _receipt_file_path(sales_id)
        if not os.path.exists(receipt_file):
            return jsonify({
                "success": False,
                "message": "Receipt not found. Please generate receipt first.",
            }), 404

        with open(receipt_file, "r") as f:
            receipt_data = json.load(f)

        html_content = generate_receipt_html(receipt_data)
        pdf_buffer = build_receipt_pdf(receipt_data)

        msg = EmailMessage()
        msg["Subject"] = f"Receipt {sales_id} - EDMA ELECTRICALS"
        msg["From"] = RECEIPT_EMAIL_ADDRESS
        msg["To"] = email
        msg.set_content(
            "Your receipt is attached. Please view this email in an HTML-compatible client to see it inline."
        )
        msg.add_alternative(html_content, subtype="html")

        if os.path.exists(LOGO_PATH):
            html_part = msg.get_body(preferencelist=("html",))
            with open(LOGO_PATH, "rb") as f:
                html_part.add_related(f.read(), maintype="image", subtype="png", cid=f"<{LOGO_CID}>")

        msg.add_attachment(
            pdf_buffer.read(),
            maintype="application",
            subtype="pdf",
            filename=f"receipt_{sales_id}.pdf",
        )

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(RECEIPT_EMAIL_ADDRESS, RECEIPT_EMAIL_PASSWORD)
            server.send_message(msg)

        return jsonify({"success": True, "message": f"Receipt sent to {email}"})

    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500
