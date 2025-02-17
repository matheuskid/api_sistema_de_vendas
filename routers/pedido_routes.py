from fastapi import APIRouter, HTTPException, Query
from Models.models import (
    Pedido, 
    ItemPedido, 
    PaginatedResponse, 
    StatusPedidoEnum,
    Cliente,
    Produto
)
from Context.database import engine
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, date
from odmantic import Model, ObjectId

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])

class ProdutoPedido(Model):
    quantidade: int
    preco_unitario: float

class PedidoCreate(Model):
    cliente_id: ObjectId
    itens: List[ProdutoPedido]

class PedidoUpdate(BaseModel):
    status: Optional[str] = None
    itens: Optional[List[dict]] = None

# Modelos de resposta
class ProdutoResponse(BaseModel):
    id: int
    nome: str
    categoria: str
    preco: float

class ItemPedidoResponse(BaseModel):
    id: int
    quantidade: int
    preco_unitario: float
    subtotal: float
    produto: ProdutoResponse

class PedidoResponse(BaseModel):
    id: int
    data_pedido: datetime
    valor_total: float
    status: str  # Aqui vamos retornar o nome do status
    cliente_nome: str
    itens: List[ItemPedidoResponse]

    class Config:
        from_attributes = True

@router.post("/", response_model=Pedido)
async def criar_pedido(pedido_data: PedidoCreate):


    # FAZER COM TRANSACTION



    try:
        # Verifica se o cliente existe
        cliente = engine.find(Cliente, Cliente.id == pedido_data.cliente_id)
        if not cliente:
            raise HTTPException(
                status_code=404,
                detail=f"Cliente com ID {pedido_data.cliente_id} não encontrado"
            )

        # Busca o status inicial (Pendente)
        status_inicial = StatusPedidoEnum.PENDENTE

        # Criar o pedido
        novo_pedido = Pedido(
            cliente_id=pedido_data.cliente_id,
            status = status_inicial,
            valor_total=0
        )

        async with engine.transaction() as transaction:
            await transaction.save(novo_pedido)

            valor_total = 0
            # Adicionar os itens do pedido
            for item in pedido_data.itens:
                # Verifica se o produto existe
                produto = await transaction.find_one(Produto, Produto.id == item.id)
                if not produto:
                    await transaction.abort()
                    raise HTTPException(
                        status_code=404,
                        detail=f"Produto com ID {item.id} não encontrado"
                    )

                # Verifica se há estoque suficiente
                if produto.estoque < item.quantidade:
                    await transaction.abort()
                    raise HTTPException(
                        status_code=400,
                        detail=f"Estoque insuficiente para o produto {produto.nome}. Disponível: {produto.estoque}"
                    )

                item_pedido = ItemPedido(
                    pedido_id=novo_pedido.id,
                    produto_id=item.id,
                    quantidade=item.quantidade,
                    preco_unitario=item.preco_unitario
                )
                valor_total += item.quantidade * item.preco_unitario
                await transaction.save(item_pedido)

                # Atualiza o estoque do produto
                produto.estoque -= item.quantidade
                await transaction.save(produto)

            # Atualiza o valor total do pedido
            novo_pedido.valor_total = valor_total
            await transaction.save(novo_pedido)
            await transaction.commit()
            return novo_pedido
        
    except HTTPException as e:
        raise HTTPException(status_code=500, detail=f"Erro ao criar pedido: {str(e)}")

'''
@router.get("/", response_model=PaginatedResponse[PedidoResponse])
def listar_pedidos(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100)
):
    try:
        offset = (page - 1) * size
        total = session.exec(select(func.count(Pedido.id))).one()
        
        # Ajustando a query para garantir o carregamento dos itens
        query = (
            select(Pedido)
            .options(
                selectinload(Pedido.cliente),
                selectinload(Pedido.status),
                selectinload(Pedido.itens).selectinload(ItemPedido.produto)
            )
            .offset(offset)
            .limit(size)
        )
        
        pedidos = session.exec(query).all()
        
        # Formata a resposta com verificação de segurança e debug
        items = []
        for pedido in pedidos:
            itens_pedido = []
            for item in pedido.itens:
                if item.produto:  # Verifica se o produto existe
                    itens_pedido.append(
                        ItemPedidoResponse(
                            id=item.id,
                            quantidade=item.quantidade,
                            preco_unitario=item.preco_unitario,
                            subtotal=item.quantidade * item.preco_unitario,
                            produto=ProdutoResponse(
                                id=item.produto.id,
                                nome=item.produto.nome,
                                categoria=item.produto.categoria,
                                preco=item.produto.preco
                            )
                        )
                    )
            
            items.append(
                PedidoResponse(
                    id=pedido.id,
                    data_pedido=pedido.data_pedido,
                    valor_total=pedido.valor_total,
                    status=pedido.status.nome.value if pedido.status else "Status não definido",
                    cliente_nome=pedido.cliente.nome if pedido.cliente else "Cliente não encontrado",
                    itens=itens_pedido
                )
            )
        
        pages = -(-total // size)
        
        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            size=size,
            pages=pages
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar pedidos: {str(e)}")

@router.get("/{pedido_id}", response_model=PedidoResponse)
def buscar_pedido(pedido_id: int, session: Session = Depends(get_session)):
    try:
        # Ajustando a query para garantir o carregamento dos itens
        pedido = session.exec(
            select(Pedido)
            .where(Pedido.id == pedido_id)
            .options(
                selectinload(Pedido.cliente),
                selectinload(Pedido.status),
                selectinload(Pedido.itens).selectinload(ItemPedido.produto)
            )
        ).first()
        
        if not pedido:
            raise HTTPException(status_code=404, detail="Pedido não encontrado")
        
        # Construir a lista de itens com verificação
        itens_pedido = []
        for item in pedido.itens:
            if item.produto:  # Verifica se o produto existe
                itens_pedido.append(
                    ItemPedidoResponse(
                        id=item.id,
                        quantidade=item.quantidade,
                        preco_unitario=item.preco_unitario,
                        subtotal=item.quantidade * item.preco_unitario,
                        produto=ProdutoResponse(
                            id=item.produto.id,
                            nome=item.produto.nome,
                            categoria=item.produto.categoria,
                            preco=item.produto.preco
                        )
                    )
                )
        
        # Construir a resposta com verificações de segurança
        return PedidoResponse(
            id=pedido.id,
            data_pedido=pedido.data_pedido,
            valor_total=pedido.valor_total,
            status=pedido.status.nome.value if pedido.status else "Status não definido",
            cliente_nome=pedido.cliente.nome if pedido.cliente else "Cliente não encontrado",
            itens=itens_pedido
        )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar pedido: {str(e)}")

@router.get("/cliente/{cliente_id}", description="Lista pedidos de um cliente específico")
def listar_pedidos_cliente(cliente_id: int, session: Session = Depends(get_session)) -> list[Pedido]:
    try:
        query = (
            select(Pedido)
            .where(Pedido.cliente_id == cliente_id)
            .options(
                selectinload(Pedido.itens).selectinload(ItemPedido.produto)
            )
        )
        return session.exec(query).all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar pedidos: {str(e)}")

@router.get("/buscar-por-data", description="Lista pedidos por data")
def listar_pedidos_por_data(
    data: str = Query(
        ..., 
        pattern=r"^\d{2}/\d{2}/\d{4}$",
        example="20/03/2024",
        description="Data no formato DD/MM/YYYY"
    ),
    session: Session = Depends(get_session)
) -> list[Pedido]:
    try:
        # Converte a data do formato BR para o formato do banco
        dia, mes, ano = data.split('/')
        data_formatada = date(int(ano), int(mes), int(dia))
        
        return session.exec(select(Pedido).where(func.date(Pedido.data_pedido) == data_formatada)).all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar pedidos: {str(e)}")

@router.get("/{pedido_id}/itens", description="Lista todos os itens de um pedido específico")
def listar_itens_pedido(pedido_id: int, session: Session = Depends(get_session)):
    try:
       
        query = (
            select(ItemPedido)
            .where(ItemPedido.pedido_id == pedido_id)
            .options(
                selectinload(ItemPedido.produto), 
                selectinload(ItemPedido.pedido)  
            )
        )
        
        itens = session.exec(query).all()
        
        if not itens:
            raise HTTPException(status_code=404, detail="Nenhum item encontrado para este pedido")
        
        
        return {
            "pedido_id": pedido_id,
            "total_itens": len(itens),
            "valor_total": sum(item.quantidade * item.preco_unitario for item in itens),
            "itens": [
                {
                    "item_id": item.id,
                    "quantidade": item.quantidade,
                    "preco_unitario": item.preco_unitario,
                    "subtotal": item.quantidade * item.preco_unitario,
                    "produto": {
                        "id": item.produto.id,
                        "nome": item.produto.nome,
                        "categoria": item.produto.categoria,
                        "preco_atual": item.produto.preco
                    }
                } for item in itens
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar itens do pedido: {str(e)}")

@router.put("/{pedido_id}", response_model=Pedido)
def atualizar_pedido(pedido_id: int, pedido_update: PedidoUpdate, session: Session = Depends(get_session)):
    try:
        # Busca o pedido
        pedido = session.get(Pedido, pedido_id)
        if not pedido:
            raise HTTPException(status_code=404, detail="Pedido não encontrado")

        # Atualiza o status se fornecido
        if pedido_update.status:
            status = session.exec(
                select(StatusPedido)
                .where(StatusPedido.nome == pedido_update.status)
            ).first()
            
            if not status:
                raise HTTPException(status_code=404, detail="Status não encontrado")
                
            pedido.status_id = status.id

        # Atualiza os itens se fornecidos
        if pedido_update.itens:
            # Remove os itens antigos
            session.exec(
                delete(ItemPedido).where(ItemPedido.pedido_id == pedido_id)
            )
            
            # Adiciona os novos itens
            valor_total = 0
            for item in pedido_update.itens:
                novo_item = ItemPedido(
                    pedido_id=pedido_id,
                    produto_id=item["produto_id"],
                    quantidade=item["quantidade"],
                    preco_unitario=item["preco_unitario"]
                )
                valor_total += item["quantidade"] * item["preco_unitario"]
                session.add(novo_item)
            
            # Atualiza o valor total do pedido
            pedido.valor_total = valor_total

        session.add(pedido)
        session.commit()
        session.refresh(pedido)
        
        # Retorna o pedido atualizado com todos os relacionamentos
        return session.exec(
            select(Pedido)
            .where(Pedido.id == pedido_id)
            .options(
                selectinload(Pedido.cliente),
                selectinload(Pedido.status),
                selectinload(Pedido.itens).selectinload(ItemPedido.produto)
            )
        ).first()
        
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar pedido: {str(e)}")

@router.delete("/{pedido_id}", description="Remove um pedido e seus itens")
def deletar_pedido(pedido_id: int, session: Session = Depends(get_session)):
    try:
       
        pedido = session.get(Pedido, pedido_id)
        if not pedido:
            raise HTTPException(status_code=404, detail="Pedido não encontrado")
        
        # 1. Primeiro deleta os itens do pedido (tabela ItemPedido)
        session.exec(
            delete(ItemPedido).where(ItemPedido.pedido_id == pedido_id)
        )
     
        session.delete(pedido)
        session.commit()
        
        return {
            "message": "Pedido removido com sucesso",
            "pedido_id": pedido_id,
            "status": "deleted"
        }
    
    except Exception as e:
        session.rollback()  
        raise HTTPException(
            status_code=500, 
            detail=f"Erro ao remover pedido: {str(e)}"
        )
'''