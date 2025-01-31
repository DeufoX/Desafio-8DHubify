from fastapi import Depends, FastAPI, HTTPException, Query
from sqlmodel import Field, Session, SQLModel, create_engine, select, Relationship
from typing import Annotated
from contextlib import asynccontextmanager


# Modelos
class Lead(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    nome: str = Field(index=True)
    email: str = Field(index=True)
    telefone: str = Field(index=True)
    negociacoes: list["Negociacao"] = Relationship(back_populates="lead") # Relação entre os modelos Lead e Negociacao


class Negociacao(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    titulo: str = Field(index=True)
    status: str | None = Field(index=True, default="em_negociacao")
    lead_id: int | None = Field(default=None, foreign_key="lead.id")
    lead: Lead | None = Relationship(back_populates="negociacoes") # Relação entre os modelos Lead e Negociacao
    funil: int | None = Field(default=None, foreign_key="funil.id")


class Funil(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    nome: str = Field(index=True)


# Conexão com o banco de dados
sqlite_file_name = "database.db" 
sqlite_url = f"sqlite:///{sqlite_file_name}" # Url de conexão com o banco de dados

connect_arg = {"check_same_thread": False} # Parametro de conexão
engine = create_engine(sqlite_url, connect_args=connect_arg) # Instancia de conexão com o banco de dados


def create_db_and_tables(): # Cria as tabelas e pré popula a tabela Funil
    """Criar o banco de dados se ele não existir
    Criar os funis se eles não existirem"""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        ganha = session.get(Funil, 1)
        perdida = session.get(Funil, 2)
        if not ganha:
            ganha = Funil(nome="ganha")
            session.add(ganha)
        if not perdida:
            perdida = Funil(nome="perdida")
            session.add(perdida)
        session.commit()


# Injeção de dependências para sessão de bando de dados
def get_session(): # Cria uma sessão reutilizavel para comunicação com o DB
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)] # Cria um tipo de dependencia para as views utilizarem

# Realiza procedimento de setup para utilização do DB
@asynccontextmanager 
async def lifespan(app):
    create_db_and_tables()
    yield


# Views
app = FastAPI(lifespan=lifespan)


@app.post("/leads/")
def create_lead(lead: Lead, session: SessionDep) -> Lead:
    session.add(lead)
    session.commit()
    session.refresh(lead)
    return lead


@app.get("/leads/")
def list_leads(
    session: SessionDep,
    offset: int = 0,
    limit: Annotated[int, Query(le=100)] = 100,
) -> list[Lead]:
    query = select(Lead).offset(offset).limit(limit)
    lead = session.exec(query).all()
    return lead


@app.get("/leads/{lead_id}")
def read_lead(lead_id: int, session: SessionDep) -> Lead:
    lead = session.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@app.post("/negociacoes/")
def create_negociacao(negociacao: Negociacao, session: SessionDep) -> Negociacao:
    if negociacao.status not in ["em_negociacao", "perdida", "ganha"]:
        raise HTTPException(
            status_code=400,
            detail=f"Valor não é <em_negociacao, perdida ou ganha> (valor '{negociacao.status}' recebido)",
        )
    lead = session.get(Lead, negociacao.lead_id)
    if not lead:
        raise HTTPException(status_code=400, detail="Id de lead inexistente")
    del negociacao.lead_id
    negociacao.lead = lead
    session.add(negociacao)
    session.commit()
    session.refresh(negociacao)
    return negociacao


@app.get("/negociacoes/")
def list_negociacoes(
    session: SessionDep,
    offset: int = 0,
    limit: Annotated[int, Query(le=100)] = 100,
) -> list[Negociacao]:
    query = select(Negociacao).offset(offset).limit(limit)
    negociacao = session.exec(query).all()
    return negociacao


@app.get("/negociacoes/{negociacao_id}")
def read_negociacao(negociacao_id: int, session: SessionDep) -> Negociacao:
    negociacao = session.get(Negociacao, negociacao_id)
    if not negociacao:
        raise HTTPException(status_code=404, detail="Negociacao not found")
    return negociacao


@app.put("/negociacoes/{negociacao_id}/change_funil_to/{novo_funil}")
def update_funil(
    negociacao_id: int, novo_funil: int, session: SessionDep
) -> Negociacao:
    negociacao = session.get(Negociacao, negociacao_id)
    funil = session.get(Funil, novo_funil)
    if not negociacao:
        raise HTTPException(status_code=404, detail="Negociacao not found")
    if not funil:
        raise HTTPException(status_code=404, detail="Funil not found")
    negociacao.funil = funil.id
    negociacao.status = funil.nome
    session.add(negociacao)
    session.commit()
    session.refresh(negociacao)
    return negociacao
