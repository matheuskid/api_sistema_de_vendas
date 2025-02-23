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
from datetime import datetime, date, time
from odmantic import Model, ObjectId

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])

class ProdutoPedido(BaseModel):
    produto_id: str
    quantidade: int

class PedidoCreate(BaseModel):
    cliente_id: str
    itens: List[ProdutoPedido]

class PedidoUpdate(BaseModel):
    status: Optional[str] = None
    itens: Optional[List[dict]] = None

# Modelos de resposta
class ProdutoResponse(BaseModel):
    id: str
    nome: str
    categoria: str
    preco: float

class ItemPedidoResponse(BaseModel):
    id: str
    quantidade: int
    preco_unitario: float
    subtotal: float
    produto: ProdutoResponse

class ClienteResponse(BaseModel):
    id: str
    nome: str
    email: str
    telefone: str
    endereco: str

class PedidoResponse(BaseModel):
    id: str
    data_pedido: datetime
    valor_total: float
    status: str
    cliente: ClienteResponse
    itens: List[ItemPedidoResponse]

    class Config:
        from_attributes = True

@router.post("/", response_model=PedidoResponse)
async def criar_pedido(pedido_data: PedidoCreate):
    try:
        # Converte a string do cliente_id para ObjectId
        cliente = await engine.find_one(Cliente, Cliente.id == ObjectId(pedido_data.cliente_id))
        if not cliente:
            raise HTTPException(
                status_code=404,
                detail=f"Cliente com ID {pedido_data.cliente_id} não encontrado"
            )

        # Criar o pedido
        novo_pedido = Pedido(
            cliente_id=ObjectId(pedido_data.cliente_id),  # Converte para ObjectId
            status=StatusPedidoEnum.PENDENTE.value,
            valor_total=0
        )

        async with engine.transaction() as transaction:
            await transaction.save(novo_pedido)

            valor_total = 0
            itens_formatados = []
            
            for item in pedido_data.itens:
                # Converte a string do produto_id para ObjectId
                produto = await transaction.find_one(Produto, Produto.id == ObjectId(item.produto_id))
                if not produto:
                    await transaction.abort()
                    raise HTTPException(
                        status_code=404,
                        detail=f"Produto com ID {item.produto_id} não encontrado"
                    )

                # Verifica se há estoque suficiente
                if produto.estoque < item.quantidade:
                    await transaction.abort()
                    raise HTTPException(
                        status_code=400,
                        detail=f"Estoque insuficiente para o produto {produto.nome}. Disponível: {produto.estoque}"
                    )

                # Cria o item do pedido
                item_pedido = ItemPedido(
                    pedido_id=novo_pedido.id,
                    produto_id=ObjectId(item.produto_id),  # Converte para ObjectId
                    quantidade=item.quantidade,
                    preco_unitario=produto.preco
                )
                await transaction.save(item_pedido)

                # Atualiza o estoque do produto
                produto.estoque -= item.quantidade
                await transaction.save(produto)

                # Calcula o subtotal e adiciona ao valor total
                subtotal = item.quantidade * produto.preco
                valor_total += subtotal

                # Formata o item para a resposta
                itens_formatados.append(
                    ItemPedidoResponse(
                        id=str(item_pedido.id),
                        quantidade=item.quantidade,
                        preco_unitario=produto.preco,
                        subtotal=subtotal,
                        produto=ProdutoResponse(
                            id=str(produto.id),
                            nome=produto.nome,
                            categoria=produto.categoria,
                            preco=produto.preco
                        )
                    )
                )

            # Atualiza o valor total do pedido
            novo_pedido.valor_total = valor_total
            await transaction.save(novo_pedido)
            await transaction.commit()

            # Retorna o pedido formatado
            return PedidoResponse(
                id=str(novo_pedido.id),
                data_pedido=novo_pedido.data_pedido,
                valor_total=novo_pedido.valor_total,
                status=novo_pedido.status,
                cliente=ClienteResponse(
                    id=str(cliente.id),
                    nome=cliente.nome,
                    email=cliente.email,
                    telefone=cliente.telefone,
                    endereco=cliente.endereco
                ),
                itens=itens_formatados
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao criar pedido: {str(e)}")



@router.get("/", response_model=PaginatedResponse[PedidoResponse])
async def listar_pedidos(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100)
):
    try:
        skip = (page - 1) * size
        
        # Obtém o total de documentos
        total = await engine.count(Pedido)
        
        # Se não houver pedidos, retorna resposta vazia
        if total == 0:
            return PaginatedResponse(
                items=[],
                total=0,
                page=page,
                size=size,
                pages=0
            )
        
        # Busca os pedidos com paginação
        pedidos = await engine.find(Pedido, skip=skip, limit=size)
        
        items = []
        for pedido in pedidos:
            # Busca cliente e itens relacionados
            cliente = await engine.find_one(Cliente, Cliente.id == pedido.cliente_id)
            itens_pedido = await engine.find(ItemPedido, ItemPedido.pedido_id == pedido.id)
            
            itens_formatados = []
            for item in itens_pedido:
                produto = await engine.find_one(Produto, Produto.id == item.produto_id)
                if produto:
                    itens_formatados.append(
                        ItemPedidoResponse(
                            id=str(item.id),
                            quantidade=item.quantidade,
                            preco_unitario=item.preco_unitario,
                            subtotal=item.quantidade * item.preco_unitario,
                            produto=ProdutoResponse(
                                id=str(produto.id),
                                nome=produto.nome,
                                categoria=produto.categoria,
                                preco=produto.preco
                            )
                        )
                    )
            
            items.append(
                PedidoResponse(
                    id=str(pedido.id),
                    data_pedido=pedido.data_pedido,
                    valor_total=pedido.valor_total,
                    status=pedido.status,
                    cliente=ClienteResponse(
                        id=str(cliente.id),
                        nome=cliente.nome,
                        email=cliente.email,
                        telefone=cliente.telefone,
                        endereco=cliente.endereco
                    ) if cliente else None,
                    itens=itens_formatados
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
async def buscar_pedido(pedido_id: str):
    try:
        pedido = await engine.find_one(Pedido, Pedido.id == ObjectId(pedido_id))
        
        if not pedido:
            raise HTTPException(status_code=404, detail="Pedido não encontrado")
        
        # Busca cliente e itens relacionados
        cliente = await engine.find_one(Cliente, Cliente.id == pedido.cliente_id)
        itens_pedido = await engine.find(ItemPedido, ItemPedido.pedido_id == pedido.id)
        
        itens_formatados = []
        for item in itens_pedido:
            produto = await engine.find_one(Produto, Produto.id == item.produto_id)
            if produto:
                itens_formatados.append(
                    ItemPedidoResponse(
                        id=str(item.id),
                        quantidade=item.quantidade,
                        preco_unitario=item.preco_unitario,
                        subtotal=item.quantidade * item.preco_unitario,
                        produto=ProdutoResponse(
                            id=str(produto.id),
                            nome=produto.nome,
                            categoria=produto.categoria,
                            preco=produto.preco
                        )
                    )
                )
        
        return PedidoResponse(
            id=str(pedido.id),
            data_pedido=pedido.data_pedido,
            valor_total=pedido.valor_total,
            status=pedido.status,
            cliente=ClienteResponse(
                id=str(cliente.id),
                nome=cliente.nome,
                email=cliente.email,
                telefone=cliente.telefone,
                endereco=cliente.endereco
            ) if cliente else None,
            itens=itens_formatados
        )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar pedido: {str(e)}")

@router.get("/relatorios/cliente/{cliente_id}", response_model=dict)
async def relatorio_cliente(cliente_id: str):
    """
    Retorna um relatório detalhado de um cliente específico, incluindo:
    - Total de pedidos
    - Valor total gasto
    - Produtos mais comprados
    - Média de valor por pedido
    - Status dos pedidos
    """
    try:
        cliente = await engine.find_one(Cliente, Cliente.id == ObjectId(cliente_id))
        if not cliente:
            raise HTTPException(status_code=404, detail="Cliente não encontrado")

        # Busca todos os pedidos do cliente
        pedidos = await engine.find(Pedido, Pedido.cliente_id == ObjectId(cliente_id))
        
        # Inicializa contadores
        total_pedidos = 0
        valor_total_gasto = 0
        produtos_quantidade = {}
        status_pedidos = {}
        
        for pedido in pedidos:
            total_pedidos += 1
            valor_total_gasto += pedido.valor_total
            
            # Contagem de status
            status_pedidos[pedido.status] = status_pedidos.get(pedido.status, 0) + 1
            
            # Busca itens do pedido
            itens = await engine.find(ItemPedido, ItemPedido.pedido_id == pedido.id)
            for item in itens:
                produto = await engine.find_one(Produto, Produto.id == item.produto_id)
                if produto:
                    if produto.nome not in produtos_quantidade:
                        produtos_quantidade[produto.nome] = {
                            'quantidade': 0,
                            'valor_total': 0
                        }
                    produtos_quantidade[produto.nome]['quantidade'] += item.quantidade
                    produtos_quantidade[produto.nome]['valor_total'] += item.quantidade * item.preco_unitario

        # Organiza produtos mais comprados
        produtos_ordenados = sorted(
            produtos_quantidade.items(),
            key=lambda x: x[1]['quantidade'],
            reverse=True
        )[:5]  # Top 5 produtos

        return {
            "cliente": {
                "nome": cliente.nome,
                "email": cliente.email
            },
            "resumo_pedidos": {
                "total_pedidos": total_pedidos,
                "valor_total_gasto": valor_total_gasto,
                "media_valor_pedido": valor_total_gasto / total_pedidos if total_pedidos > 0 else 0,
                "status_pedidos": status_pedidos
            },
            "produtos_mais_comprados": [
                {
                    "produto": nome,
                    "quantidade": dados['quantidade'],
                    "valor_total": dados['valor_total']
                }
                for nome, dados in produtos_ordenados
            ]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar relatório: {str(e)}")

@router.get("/relatorios/produtos/mais-vendidos")
async def produtos_mais_vendidos(
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    categoria: Optional[str] = None,
    limit: int = Query(default=10, ge=1, le=100)
):
    try:
        # Usando o nome do banco diretamente
        database = engine.client['db']  # Nome do banco definido no .env
        collection = database['pedido']
        
        pipeline = []
        match_conditions = {}

        # Validação e processamento das datas
        if data_inicio or data_fim:
            date_filter = {}
            if data_inicio:
                inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
                inicio = inicio.replace(hour=0, minute=0, second=0, microsecond=0)
                date_filter["$gte"] = inicio
            if data_fim:
                fim = datetime.strptime(data_fim, "%Y-%m-%d")
                fim = fim.replace(hour=23, minute=59, second=59, microsecond=999999)
                date_filter["$lte"] = fim

            match_conditions["data_pedido"] = date_filter
            pipeline.append({"$match": match_conditions})

        # Pipeline de agregação
        pipeline.extend([
            {
                "$lookup": {
                    "from": "item_pedido",
                    "localField": "_id",
                    "foreignField": "pedido_id",
                    "as": "itens"
                }
            },
            {"$unwind": "$itens"},
            {
                "$lookup": {
                    "from": "produto",
                    "localField": "itens.produto_id",
                    "foreignField": "_id",
                    "as": "produto_info"
                }
            },
            {"$unwind": "$produto_info"},
        ])

        # Filtro de categoria se especificado
        if categoria:
            pipeline.append({
                "$match": {"produto_info.categoria": categoria}
            })

        # Agrupamento e cálculos
        pipeline.extend([
            {
                "$group": {
                    "_id": "$produto_info._id",
                    "nome": {"$first": "$produto_info.nome"},
                    "categoria": {"$first": "$produto_info.categoria"},
                    "quantidade_total": {"$sum": "$itens.quantidade"},
                    "valor_total": {
                        "$sum": {
                            "$multiply": ["$itens.quantidade", "$itens.preco_unitario"]
                        }
                    },
                    "numero_pedidos": {"$sum": 1},
                    "preco_atual": {"$first": "$produto_info.preco"}
                }
            },
            {
                "$project": {
                    "nome": 1,
                    "categoria": 1,
                    "quantidade_total": 1,
                    "valor_total": 1,
                    "numero_pedidos": 1,
                    "preco_atual": 1,
                    "media_valor_pedido": {
                        "$cond": [
                            {"$eq": ["$numero_pedidos", 0]},
                            0,
                            {"$divide": ["$valor_total", "$numero_pedidos"]}
                        ]
                    },
                    "ticket_medio": {
                        "$cond": [
                            {"$eq": ["$quantidade_total", 0]},
                            0,
                            {"$divide": ["$valor_total", "$quantidade_total"]}
                        ]
                    }
                }
            },
            {"$sort": {"quantidade_total": -1}},
            {"$limit": limit}
        ])

        # Debug: imprime informações sobre o banco
        print("Tentando executar agregação de produtos mais vendidos...")
        print(f"Collections disponíveis: {await database.list_collection_names()}")
        
        # Executa a agregação
        resultados = await collection.aggregate(pipeline).to_list(None)
        
        print(f"Resultados encontrados: {len(resultados) if resultados else 0}")

        return {
            "periodo": {
                "inicio": data_inicio,
                "fim": data_fim
            },
            "categoria_filtro": categoria,
            "produtos": [
                {
                    "produto_id": str(r["_id"]),
                    "nome": r["nome"],
                    "categoria": r["categoria"],
                    "quantidade_total": r["quantidade_total"],
                    "valor_total": r["valor_total"],
                    "numero_pedidos": r["numero_pedidos"],
                    "preco_atual": r["preco_atual"],
                    "media_valor_pedido": r["media_valor_pedido"],
                    "ticket_medio": r["ticket_medio"]
                }
                for r in resultados
            ]
        }

    except Exception as e:
        print(f"Erro detalhado: {str(e)}")  # Log do erro para debug
        raise HTTPException(status_code=500, detail=f"Erro ao gerar relatório: {str(e)}")

@router.get("/relatorios/vendas/diarias")
async def relatorio_vendas_diarias(
    data_inicio: Optional[str] = Query(None),
    data_fim: Optional[str] = Query(None)
):
    try:
        # Usando o nome do banco diretamente
        database = engine.client['db']  # Nome do banco definido no .env (DB_NAME = 'db')
        collection = database['pedido']
        
        pipeline = []
        match_conditions = {}

        # Validação e processamento das datas
        if data_inicio or data_fim:
            date_filter = {}
            if data_inicio:
                inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
                inicio = inicio.replace(hour=0, minute=0, second=0, microsecond=0)
                date_filter["$gte"] = inicio
            if data_fim:
                fim = datetime.strptime(data_fim, "%Y-%m-%d")
                fim = fim.replace(hour=23, minute=59, second=59, microsecond=999999)
                date_filter["$lte"] = fim

            match_conditions["data_pedido"] = date_filter
            pipeline.append({"$match": match_conditions})

        # Pipeline de agregação
        pipeline.extend([
            {
                "$lookup": {
                    "from": "item_pedido",
                    "localField": "_id",
                    "foreignField": "pedido_id",
                    "as": "itens"
                }
            },
            {
                "$addFields": {
                    "data": {
                        "$dateToString": {
                            "format": "%Y-%m-%d",
                            "date": "$data_pedido",
                            "timezone": "America/Sao_Paulo"
                        }
                    }
                }
            },
            {
                "$group": {
                    "_id": {
                        "data": "$data",
                        "status": "$status"
                    },
                    "count_status": {"$sum": 1},
                    "valor_total_status": {"$sum": "$valor_total"},
                    "produtos_vendidos_status": {
                        "$sum": {"$sum": "$itens.quantidade"}
                    }
                }
            },
            {
                "$group": {
                    "_id": "$_id.data",
                    "total_pedidos": {"$sum": "$count_status"},
                    "valor_total": {"$sum": "$valor_total_status"},
                    "produtos_vendidos": {"$sum": "$produtos_vendidos_status"},
                    "status": {
                        "$push": {
                            "k": "$_id.status",
                            "v": "$count_status"
                        }
                    }
                }
            },
            {
                "$addFields": {
                    "media_valor_pedido": {
                        "$cond": [
                            {"$eq": ["$total_pedidos", 0]},
                            0,
                            {"$divide": ["$valor_total", "$total_pedidos"]}
                        ]
                    },
                    "status": {
                        "$arrayToObject": "$status"
                    }
                }
            },
            {"$sort": {"_id": 1}}
        ])

        # Debug: imprime informações sobre o banco
        print("Tentando executar agregação...")
        print(f"Collections disponíveis: {await database.list_collection_names()}")
        
        # Executa a agregação
        resultados = await collection.aggregate(pipeline).to_list(None)
        
        print(f"Resultados encontrados: {len(resultados) if resultados else 0}")

        return {
            "periodo": {
                "inicio": data_inicio,
                "fim": data_fim
            },
            "vendas_diarias": [
                {
                    "data": r["_id"],
                    "total_pedidos": r["total_pedidos"],
                    "valor_total": r["valor_total"],
                    "produtos_vendidos": r["produtos_vendidos"],
                    "media_valor_pedido": r["media_valor_pedido"],
                    "status": r["status"]
                }
                for r in resultados
            ] if resultados else []
        }

    except Exception as e:
        print(f"Erro detalhado: {str(e)}")  # Log do erro para debug
        raise HTTPException(status_code=500, detail=f"Erro ao gerar relatório: {str(e)}")
        
