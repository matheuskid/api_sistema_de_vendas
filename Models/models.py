from datetime import datetime
from typing import Optional, List, TypeVar, Generic
from odmantic import Model, ObjectId, Field
from pydantic import BaseModel
from enum import Enum

T = TypeVar('T')

class PaginatedResponse(Model, Generic[T]):
    items: List[T]
    total: int
    page: int
    size: int
    pages: int

class Cliente(Model):
    nome: str 
    data_nascimento: str
    email: str
    telefone: str
    endereco: str
    cidade: str
    estado: str
    cep: str
    
class ClienteAtualizado(BaseModel):
    nome: Optional[str] = None
    data_nascimento: Optional[str] = None
    email: Optional[str] = None
    telefone: Optional[str] = None
    endereco: Optional[str] = None
    cidade: Optional[str] = None
    estado: Optional[str] = None
    cep: Optional[str] = None

class Produto(Model):
    nome: str
    categoria: str
    preco: float
    estoque: int

class ProdutoAtualizado(BaseModel):
    nome: Optional[str] = None
    categoria: Optional[str] = None
    preco: Optional[float] = None
    estoque: Optional[int] = None
    
class StatusPedidoEnum(str, Enum):
    PENDENTE = "Pendente"
    EM_PROCESSAMENTO = "Em Processamento"
    PAGO = "Pago"
    ENVIADO = "Enviado"
    ENTREGUE = "Entregue"
    CANCELADO = "Cancelado"

class Pedido(Model):
    cliente_id: ObjectId
    status: str
    data_pedido: datetime = Field(default_factory=datetime.now)
    valor_total: float

    model_config = {"parse_doc_with_default_factories": True}

class ItemPedido(Model):
    pedido_id: ObjectId  
    produto_id: ObjectId
    quantidade: int
    preco_unitario: float
