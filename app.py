from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import sqlite3
import os

app = FastAPI()

# 初始化数据库
def init_db():
    if not os.path.exists("inventory.db"):
        conn = sqlite3.connect("inventory.db")
        c = conn.cursor()
        c.execute('''CREATE TABLE products
                     (sku TEXT PRIMARY KEY, name TEXT, stock INTEGER)''')
        c.execute('''CREATE TABLE reservations
                     (request_id TEXT PRIMARY KEY, sku TEXT, quantity INTEGER, status TEXT)''')
        products = [
            ("BOOK", "教材", 10),
            ("PEN", "钢笔", 20),
            ("PENCIL", "铅笔", 5),
            ("ERASER", "橡皮", 0),
            ("RULER", "尺子", 15),
            ("BAG", "书包", 3),
            ("WATER", "水杯", 8),
            ("NOTE", "笔记本", 12),
            ("CUP", "马克杯", 0),
            ("DESK", "书桌", 2)
        ]
        c.executemany("INSERT INTO products VALUES (?, ?, ?)", products)
        conn.commit()
        conn.close()

init_db()

class ReserveRequest(BaseModel):
    request_id: str
    sku: str
    quantity: int

@app.get("/health")
def health():
    return {"status": "ok"}

# Web提交页面+记录列表+筛选
@app.get("/", response_class=HTMLResponse)
def web_page():
    return """
    <html>
        <body style="width:800px;margin:50px auto;">
            <h1>订单提交</h1>
            <input id="request_id" placeholder="请求编号"><br><br>
            <input id="sku" placeholder="商品编号"><br><br>
            <input id="quantity" placeholder="数量"><br><br>
            <button onclick="submit()">提交订单</button>
            <h2>扣减记录</h2>
            <button onclick="load_records('')">全部记录</button>
            <button onclick="load_records('成功')">成功记录</button>
            <div id="result"></div>
            <script>
                async function submit(){
                    const res = await fetch('/reserve',{
                        method:'POST',
                        headers:{'Content-Type':'application/json'},
                        body:JSON.stringify({
                            request_id:document.getElementById('request_id').value,
                            sku:document.getElementById('sku').value,
                            quantity:parseInt(document.getElementById('quantity').value)
                        })
                    })
                    alert(await res.text())
                    load_records('')
                }
                async function load_records(status){
                    const res = await fetch('/reservations?status='+status)
                    document.getElementById('result').innerHTML = '<pre>'+JSON.stringify(await res.json(),null,2)+'</pre>'
                }
                load_records('')
            </script>
        </body>
    </html>
    """

@app.get("/products")
def get_products():
    conn = sqlite3.connect("inventory.db")
    c = conn.cursor()
    c.execute("SELECT * FROM products")
    rows = c.fetchall()
    conn.close()
    return [{"sku": r[0], "name": r[1], "stock": r[2]} for r in rows]

@app.post("/reserve")
def reserve(req: ReserveRequest):
    if req.quantity <= 0:
        raise HTTPException(status_code=400, detail="数量必须大于0")
    conn = sqlite3.connect("inventory.db")
    c = conn.cursor()
    c.execute("SELECT * FROM reservations WHERE request_id=?", (req.request_id,))
    existing = c.fetchone()
    if existing:
        if existing[1] == req.sku and existing[2] == req.quantity:
            return {"status": "重复请求，已处理", "request_id": req.request_id}
        else:
            raise HTTPException(status_code=409, detail="请求编号已被占用")
    c.execute("SELECT stock FROM products WHERE sku=?", (req.sku,))
    product = c.fetchone()
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    stock = product[0]
    if stock < req.quantity:
        raise HTTPException(status_code=409, detail=f"库存不足，当前库存{stock}")
    c.execute("UPDATE products SET stock=stock-? WHERE sku=?", (req.quantity, req.sku))
    c.execute("INSERT INTO reservations VALUES (?, ?, ?, ?)", 
              (req.request_id, req.sku, req.quantity, "成功"))
    conn.commit()
    conn.close()
    return {"status": "成功", "request_id": req.request_id, "remaining_stock": stock - req.quantity}

@app.get("/reservations")
def get_reservations(status: str = Query(None)):
    conn = sqlite3.connect("inventory.db")
    c = conn.cursor()
    if status:
        c.execute("SELECT * FROM reservations WHERE status=?", (status,))
    else:
        c.execute("SELECT * FROM reservations")
    rows = c.fetchall()
    conn.close()
    return [{"request_id": r[0], "sku": r[1], "quantity": r[2], "status": r[3]} for r in rows]
