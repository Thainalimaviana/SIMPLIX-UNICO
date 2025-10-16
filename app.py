from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from datetime import datetime
import requests
import time
import json
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
try:
    import psycopg
except ImportError:
    psycopg = None

app = Flask(__name__)
app.secret_key = "chave_secreta"

API_LOGIN = "https://simplix-integration.partner1.com.br/api/Login"
API_SIMULATE = "https://simplix-integration.partner1.com.br/api/Proposal/Simulate"
API_ASYNC_RESULT = "https://simplix-integration.partner1.com.br/api/Proposal/SimulateAsyncResult"

TOKEN = ""
TOKEN_EXPIRA = 0
ULTIMO_TRANSACTION_ID = None

DATABASE_URL = os.environ.get("DATABASE_URL") 
DB_FILE = "users.db"

def get_conn():
    if DATABASE_URL and psycopg:
        return psycopg.connect(DATABASE_URL)
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            senha TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            background TEXT DEFAULT '#133abb,#00e1ff'
        )
    """)

    if isinstance(conn, sqlite3.Connection):
        c.execute("UPDATE users SET background = ? WHERE background = ?", ("#133abb,#00e1ff", "blue"))
    else:
        c.execute("UPDATE users SET background = %s WHERE background = %s", ("#133abb,#00e1ff", "blue"))

    if isinstance(conn, sqlite3.Connection):
        c.execute("SELECT * FROM users WHERE role = ?", ("admin",))
    else:
        c.execute("SELECT * FROM users WHERE role = %s", ("admin",))

    if not c.fetchone():
        admin_user = "Leonardo"
        admin_pass = hash_senha("Tech@2026")
        if isinstance(conn, sqlite3.Connection):
            c.execute("INSERT INTO users (nome, senha, role, background) VALUES (?, ?, ?, ?)",
                      (admin_user, admin_pass, "admin", "#133abb,#00e1ff"))
        else:
            c.execute("INSERT INTO users (nome, senha, role, background) VALUES (%s, %s, %s, %s)",
                      (admin_user, admin_pass, "admin", "#133abb,#00e1ff"))
        print("✅ Usuário admin criado: login=Leonardo senha=123456")

    conn.commit()
    conn.close()

def hash_senha(senha):
    return generate_password_hash(senha)

def verificar_senha(senha_digitada, senha_hash):
    return check_password_hash(senha_hash, senha_digitada)

def is_admin():
    return session.get("role") == "admin"

def get_user(nome):
    conn = get_conn()
    c = conn.cursor()
    if isinstance(conn, sqlite3.Connection):
        c.execute("SELECT * FROM users WHERE nome = ?", (nome,))
    else:
        c.execute("SELECT * FROM users WHERE nome = %s", (nome,))
    user = c.fetchone()
    conn.close()
    return user

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        nome = request.form["nome"]
        senha = request.form["senha"]
        user = get_user(nome)

        if user and verificar_senha(senha, user[2]):
            session["user"] = nome
            session["role"] = user[3]
            return redirect(url_for("index"))

        return render_template("login.html", erro="Login inválido")

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if "user" not in session or session.get("role") != "admin":
        return redirect(url_for("index"))

    if request.method == "POST":
        nome = request.form["nome"]
        senha = hash_senha(request.form["senha"])
        role = request.form.get("role", "user")
        try:
            conn = get_conn()
            c = conn.cursor()
            if isinstance(conn, sqlite3.Connection):
                c.execute("INSERT INTO users (nome, senha, role) VALUES (?, ?, ?)", (nome, senha, role))
            else:
                c.execute("INSERT INTO users (nome, senha, role) VALUES (%s, %s, %s)", (nome, senha, role))
            conn.commit()
            conn.close()
            return redirect(url_for("gerenciar_usuarios"))
        except Exception as e:
            print("Erro ao registrar:", e)
            return render_template("register.html", erro="Nome já existe!")
    return render_template("register.html")

@app.route("/usuarios")
def gerenciar_usuarios():
    if "user" not in session or session.get("role") != "admin":
        return redirect(url_for("index"))

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, nome, role FROM users")
    usuarios = c.fetchall()
    conn.close()
    return render_template("usuarios.html", usuarios=usuarios)

@app.route("/esteira")
def esteira():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_conn()
    c = conn.cursor()

    if isinstance(conn, sqlite3.Connection):
        c.execute("""
            CREATE TABLE IF NOT EXISTS esteira (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                digitador TEXT NOT NULL,
                cpf TEXT NOT NULL,
                bancarizadora TEXT,
                data_hora TEXT,
                valor_contrato REAL
            )
        """)
        c.execute("SELECT digitador, cpf, bancarizadora, data_hora, valor_contrato FROM esteira ORDER BY id DESC")
    else:
        c.execute("""
            CREATE TABLE IF NOT EXISTS esteira (
                id SERIAL PRIMARY KEY,
                digitador TEXT NOT NULL,
                cpf TEXT NOT NULL,
                bancarizadora TEXT,
                data_hora TEXT,
                valor_contrato REAL
            )
        """)
        c.execute("SELECT digitador, cpf, bancarizadora, data_hora, valor_contrato FROM esteira ORDER BY id DESC")

    registros = c.fetchall()
    conn.close()

    return render_template("esteira.html", registros=registros)

@app.route("/excluir/<int:user_id>", methods=["POST"])
def excluir_usuario(user_id):
    if "user" not in session or session.get("role") != "admin":
        return redirect(url_for("index"))

    conn = get_conn()
    c = conn.cursor()
    if isinstance(conn, sqlite3.Connection):
        c.execute("DELETE FROM users WHERE id = ?", (user_id,))
    else:
        c.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("gerenciar_usuarios"))

@app.route("/editar/<int:user_id>", methods=["GET", "POST"])
def editar_usuario(user_id):
    if "user" not in session or session.get("role") != "admin":
        return redirect(url_for("index"))

    conn = get_conn()
    c = conn.cursor()

    if isinstance(conn, sqlite3.Connection):
        c.execute("SELECT id, nome, role, background FROM users WHERE id = ?", (user_id,))
    else:
        c.execute("SELECT id, nome, role, background FROM users WHERE id = %s", (user_id,))
    user = c.fetchone()

    if not user:
        conn.close()
        return "Usuário não encontrado", 404

    if request.method == "POST":
        novo_nome = request.form["nome"]
        nova_senha = request.form["senha"]
        novo_background = request.form.get("background", user[3] if len(user) > 3 else "#133abb,#00e1ff")

        if nova_senha.strip():
            senha_hash = hash_senha(nova_senha)
            if isinstance(conn, sqlite3.Connection):
                c.execute("UPDATE users SET nome = ?, senha = ?, background = ? WHERE id = ?",
                          (novo_nome, senha_hash, novo_background, user_id))
            else:
                c.execute("UPDATE users SET nome = %s, senha = %s, background = %s WHERE id = %s",
                          (novo_nome, senha_hash, novo_background, user_id))
        else:
            if isinstance(conn, sqlite3.Connection):
                c.execute("UPDATE users SET nome = ?, background = ? WHERE id = ?",
                          (novo_nome, novo_background, user_id))
            else:
                c.execute("UPDATE users SET nome = %s, background = %s WHERE id = %s",
                          (novo_nome, novo_background, user_id))

        conn.commit()
        conn.close()
        return redirect(url_for("gerenciar_usuarios"))

    conn.close()
    return render_template("editar.html", user=user)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/index")
def index():
    if "user" not in session:
        return redirect(url_for("login"))

    cor1 = session.get("cor1", "#133abb")
    cor2 = session.get("cor2", "#00e1ff")

    return render_template("index.html",
                           usuario=session["user"],
                           cor1=cor1,
                           cor2=cor2)

def gerar_token():
    global TOKEN_EXPIRA
    try:
        dados = {"username": "477f702a-4a6f-4b02-b5eb-afcd38da99f8", "password": "b5iTIZ2n"}
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        resp = requests.post(API_LOGIN, json=dados, headers=headers, timeout=10)
        if resp.status_code == 200 and resp.json().get("success"):
            token = resp.json()["objectReturn"]["access_token"]
            TOKEN_EXPIRA = time.time() + 3600 - 60
            print(f"[TOKEN] Gerado com sucesso")
            return token
    except Exception as e:
        print(f"Erro ao gerar token: {e}")
    return ""

def obter_token():
    global TOKEN
    if not TOKEN or time.time() >= TOKEN_EXPIRA:
        TOKEN = gerar_token()
    return TOKEN

@app.before_request
def ensure_db():
    if not hasattr(app, "_db_initialized"):
        try:
            init_db()
            print("✅ Banco inicializado (uma única vez)")
        except Exception as e:
            print(f"⚠️ Erro ao inicializar banco: {e}")
        app._db_initialized = True 

@app.route("/cadastrar")
def cadastrar():
    return render_template("cadastrar.html")

@app.route("/simplix-passo12", methods=["POST"])
def simplix_passo12():
    global ULTIMO_TRANSACTION_ID
    data = request.get_json()
    cpf = data.get("cpf")
    token = obter_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    payload1 = {
        "cpf": cpf,
        "callBackBalance": {
            "url": "https://webhook.site/82d16202-0406-4088-bfd7-82edf9d23497",
            "method": "POST"
        }
    }

    try:
        print(f"\n[DEBUG] Enviando PASSO 1 (balance-request)...")
        resp1 = requests.post(
            "https://simplix-integration.partner1.com.br/api/Fgts/balance-request",
            json=payload1,
            headers=headers,
            timeout=60
        )

        print(f"[DEBUG] Status PASSO 1: {resp1.status_code}")
        print(f"[DEBUG] Resposta PASSO 1: {resp1.text}")

        data1 = resp1.json()
        transactionId = data1.get("objectReturn", {}).get("transactionId")

        if not transactionId:
            print("[ERRO] Nenhum transactionId retornado.")
            return jsonify({
                "sucesso": False,
                "mensagem": "Erro no passo 1 — Simplix não retornou transactionId",
                "retorno": data1
            }), 400

        print(f"[PASSO 1 ✅] TransactionId gerado: {transactionId}")
        ULTIMO_TRANSACTION_ID = transactionId

    except Exception as e:
        print(f"[FALHA NO PASSO 1 ❌] {e}")
        return jsonify({"sucesso": False, "mensagem": f"Erro no passo 1: {e}"}), 500

    payload2 = {
        "transactionId": transactionId,
        "callBackSimulate": {
            "url": "https://webhook.site/82d16202-0406-4088-bfd7-82edf9d23497",
            "method": "POST"
        }
    }

    tabelas = []
    ultima_desc = None
    mensagens_api = []
    desc_final = None

    print(f"[DEBUG] Iniciando PASSO 2 (simulate com re-tentativas)...")

    for tentativa in range(10):
        try:
            resp2 = requests.post(
                "https://simplix-integration.partner1.com.br/api/Fgts/simulate",
                json=payload2,
                headers=headers,
                timeout=60
            )

            print(f"[DEBUG] Tentativa {tentativa + 1} - Status: {resp2.status_code}")
            print(f"[DEBUG] Resposta PASSO 2: {resp2.text}")

            try:
                data2 = resp2.json()
            except Exception:
                data2 = json.loads(resp2.text.strip() or "{}")

            retorno = data2.get("objectReturn", {}).get("retornoSimulacao", [])
            desc_atual = data2.get("objectReturn", {}).get("description")

            if desc_atual:
                mensagens_api.append(desc_atual)
                ultima_desc = desc_atual

            if retorno:
                for t in retorno:
                    tabelas.append({
                        "bancarizadora": t.get("bancarizadora"),
                        "tabelaTitulo": t.get("tabelaTitulo"),
                        "tabelaId": t.get("tabelaId"),
                        "simulationId": t.get("simulationId"),
                        "valorLiquido": t.get("valorLiquido", 0),
                        "taxa": (t.get("detalhes") or {}).get("taxa", 0),
                        "tc": (t.get("detalhes") or {}).get("tc", 0),
                        "parcelas": (t.get("detalhes") or {}).get("parcelas", [])
                    })
                print(f"[PASSO 2 ✅] {len(tabelas)} tabelas retornadas na tentativa {tentativa + 1}.")
                break
            else:
                print(f"[AGUARDANDO] Tentativa {tentativa + 1}/10 — resultados ainda não disponíveis...")
                time.sleep(3)

        except Exception as e:
            print(f"[ERRO AO CONSULTAR SIMULATE ❌] {e}")
            time.sleep(3)

    if not tabelas:
        print("[FINAL ❌] Nenhuma tabela retornada após todas as tentativas.")
        print("[EXTRA 🔄] Tentando consulta direta final (modo síncrono)...")

        try:
            tentativa_sincrona = 0
            while tentativa_sincrona < 3:
                tentativa_sincrona += 1
                print(f"[SINCRONO 🔁] Tentativa {tentativa_sincrona}/3 (modo síncrono)...")

                resp_final = requests.post(
                    "https://simplix-integration.partner1.com.br/api/Proposal/Simulate",
                    json={"cpf": cpf},
                    headers=headers,
                    timeout=60
                )

                print(f"[DEBUG] Status consulta direta: {resp_final.status_code}")
                print(f"[DEBUG] Resposta direta: {resp_final.text}")

                try:
                    data_final = resp_final.json()
                except Exception:
                    data_final = {}

                retorno_final = data_final.get("objectReturn", {}).get("retornoSimulacao", [])
                desc_final = (
                    data_final.get("objectReturn", {}).get("description")
                    or data_final.get("objectReturn", {}).get("observacao")
                    or data_final.get("message")
                    or "Sem descrição disponível"
                )

                if retorno_final:
                    for t in retorno_final:
                        tabelas.append({
                            "bancarizadora": t.get("bancarizadora"),
                            "tabelaTitulo": t.get("tabelaTitulo"),
                            "tabelaId": t.get("tabelaId"),
                            "simulationId": t.get("simulationId"),
                            "valorLiquido": t.get("valorLiquido", 0),
                            "taxa": (t.get("detalhes") or {}).get("taxa", 0),
                            "tc": (t.get("detalhes") or {}).get("tc", 0),
                            "parcelas": (t.get("detalhes") or {}).get("parcelas", [])
                        })
                    print("[FINAL ✅] Resultado obtido pela consulta direta.")
                    break

                if desc_final and "limite" in desc_final.lower():
                    if tentativa_sincrona < 3:
                        print("[INFO ⏳] Limite de requisições — aguardando 10s para nova tentativa...")
                        time.sleep(10)
                        continue
                    else:
                        print("[INFO ⚠️] Limite de tentativas síncronas atingido (3x). Encerrando.")
                        break
                else:
                    break

            ultima_desc = desc_final or ultima_desc
            print(f"[FINAL ❌] Consulta direta sem retorno. Descrição: {ultima_desc}")

        except Exception as e:
            print(f"[ERRO AO CONSULTAR DIRETO ❌] {e}")
            desc_final = f"Erro ao consultar direto: {e}"

    if not tabelas:
        return jsonify({
            "sucesso": False,
            "mensagem": desc_final or ultima_desc or "Nenhuma tabela disponível (verifique o CPF ou aguarde alguns segundos)",
            "desc_final": desc_final,
            "objectReturn": {
                "description": ultima_desc or desc_final or "Sem descrição"
            },
            "transactionId": transactionId
        }), 400

    print(f"[FINAL ✅] Enviando {len(tabelas)} tabelas ao front.")
    return jsonify({
        "sucesso": True,
        "transactionId": transactionId,
        "tabelas": tabelas
    })

@app.route("/simplix-cadastrar", methods=["POST"])
def simplix_cadastrar():
    try:
        payload = request.get_json(force=True)
        token = obter_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        cliente = payload.get("cliente", {})
        endereco = cliente.get("endereco", {})
        conta = cliente.get("contaBancaria", {})

        cliente["endereco"] = {
            "Cep": endereco.get("cep", ""),
            "Bairro": endereco.get("bairro", ""),
            "Cidade": endereco.get("cidade", ""),
            "Estado": endereco.get("estado", ""),
            "Numero": endereco.get("numero", ""),
            "Logradouro": endereco.get("logradouro", ""),
            "Complemento": endereco.get("complemento", "")
        }

        cliente["contaBancaria"] = {
            "conta": conta.get("conta", ""),
            "agencia": conta.get("agencia", ""),
            "tipoDeConta": conta.get("tipoDeConta", ""),
            "codigoDoBanco": conta.get("codigoDoBanco", ""),
            "digitoDaConta": conta.get("digitoDaConta", ""),
            "tipoDeOperacao": conta.get("tipoDeOperacao", "Transferencia")
        }

        payload["cliente"] = cliente

        print("\n[DEBUG] === Enviando para Simplix /Proposal/Create ===")
        print(json.dumps(payload, indent=2, ensure_ascii=False))

        response = requests.post(
            "https://simplix-integration.partner1.com.br/api/Proposal/Create",
            headers=headers,
            json=payload,
            timeout=90
        )

        print(f"[DEBUG] Status: {response.status_code}")
        print(f"[DEBUG] Resposta: {response.text}")

        try:
            data = response.json()
            if response.status_code == 200 and data.get("success", False):
                conn = get_conn()
                c = conn.cursor()

                if isinstance(conn, sqlite3.Connection):
                    c.execute("""
                        CREATE TABLE IF NOT EXISTS esteira (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            digitador TEXT NOT NULL,
                            cpf TEXT NOT NULL,
                            bancarizadora TEXT,
                            data_hora TEXT,
                            valor_contrato REAL
                        )
                    """)
                else:
                    c.execute("""
                        CREATE TABLE IF NOT EXISTS esteira (
                            id SERIAL PRIMARY KEY,
                            digitador TEXT NOT NULL,
                            cpf TEXT NOT NULL,
                            bancarizadora TEXT,
                            data_hora TEXT,
                            valor_contrato REAL
                        )
                    """)

                digitador = session.get("user", "Desconhecido")
                cpf = payload["cliente"]["cpf"]
                bancarizadora = payload.get("operacao", {}).get("bancarizadora", "Não informado")
                valor_contrato = payload.get("operacao", {}).get("valorLiquido", 0)
                data_hora = datetime.now().strftime("%d/%m/%Y %H:%M")

                c.execute("""
                    INSERT INTO esteira (digitador, cpf, bancarizadora, data_hora, valor_contrato)
                    VALUES (?, ?, ?, ?, ?)
                """, (digitador, cpf, bancarizadora, data_hora, valor_contrato))

                conn.commit()
                conn.close()
                print(f"[ESTEIRA] ✅ Proposta salva: {cpf} - {valor_contrato}")

        except Exception as e:
            print(f"[ERRO ao salvar na esteira]: {e}")

        try:
            return jsonify(response.json()), response.status_code
        except Exception:
            return jsonify({"raw_response": response.text}), response.status_code

    except Exception as e:
        print(f"[ERRO /simplix-cadastrar] {e}")
        return jsonify({"erro": str(e)}), 500

@app.route("/periodos")
def listar_periodos():
    global ULTIMO_TRANSACTION_ID
    if not ULTIMO_TRANSACTION_ID:
        return jsonify({"erro": "Nenhum transactionId ativo"}), 400

    token = obter_token()
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    url = f"{API_ASYNC_RESULT}?transactionId={ULTIMO_TRANSACTION_ID}"

    try:
        resp = requests.get(url, headers=headers, timeout=60)
        data = resp.json()
        tabelas = data.get("objectReturn", {}).get("retornoSimulacao", [])
        return jsonify(tabelas)
    except Exception as e:
        return jsonify({"erro": f"Falha ao buscar tabelas: {e}"}), 500

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/index')
def index_redirect():
    return render_template('index.html')

if __name__ == "__main__":
    app.run(debug=True, port=8600)
