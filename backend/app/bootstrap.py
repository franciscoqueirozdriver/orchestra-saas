from getpass import getpass

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import User
from app.security import hash_password


def main() -> None:
    email = input("E-mail do administrador da plataforma: ").strip().lower()
    if "@" not in email or len(email) > 320:
        raise SystemExit("E-mail inválido")
    password = getpass("Senha (mínimo 12 caracteres): ")
    confirmation = getpass("Repita a senha: ")
    if password != confirmation:
        raise SystemExit("As senhas não conferem")
    try:
        password_hash = hash_password(password)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    db: Session = SessionLocal()
    try:
        if db.query(User).filter(User.role == "platform_admin").first():
            raise SystemExit("Já existe um administrador da plataforma; bootstrap recusado")
        if db.query(User).filter(User.email == email).first():
            raise SystemExit("Já existe uma conta com esse e-mail")
        user = User(email=email, password_hash=password_hash, full_name="Administrador da plataforma", role="platform_admin", tenant_id=None)
        db.add(user)
        db.commit()
        print(f"Administrador criado: {email}")
        print("Entre pelo painel e crie a primeira empresa com seu próprio usuário administrador.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
