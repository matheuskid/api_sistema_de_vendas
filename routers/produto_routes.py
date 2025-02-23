
from fastapi import APIRouter, HTTPException, Query
from Models.models import Produto, PaginatedResponse, ProdutoAtualizado
from Context.database import engine
from typing import List
from odmantic import ObjectId, query

router = APIRouter(prefix="/produtos", tags=["Produtos"])

@router.post("/",response_model=Produto, description="Insere um novo produto no sistema.")
async def inserir_produto(produto: Produto) -> Produto:
    try:
        await engine.save(produto)
        return produto
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao criar produto: {str(e)}")

# Rota paginada para Produtos
@router.get("/", response_model=PaginatedResponse[Produto], description="Lista todos os produtos com paginação")
async def listar_produtos(
    page: int = Query(default=1, ge=1, description="Número da página"),
    size: int = Query(default=10, ge=1, le=100, description="Itens por página")
) -> PaginatedResponse[Produto]:
    try:
        offset = (page - 1) * size

        total = await engine.count(Produto)
        
        # Busca items da página atual
        items = await engine.find(Produto, skip=offset, limit=size)
        
        pages = -(-total // size)
        
        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            size=size,
            pages=pages
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar produtos: {str(e)}")
    
@router.get("/{produto_id}", description="Retorna um produto existente.")
async def listar_produtos(produto_id: ObjectId) -> Produto:
    try:
        if produto_id is None:
            raise HTTPException(status_code=400, detail="ID do produto inválido.")
        
        produto = await engine.find_one(Produto, Produto.id == produto_id)

        if not produto:
            raise HTTPException(status_code=404, detail="produto não encontrado")
        
        return produto
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar produto: {str(e)}")

@router.put("/{produto_id}", description="Atualiza as informações de um produto existente.")
async def atualizar_produto(produto_id: ObjectId, produto_atualizado: ProdutoAtualizado) -> Produto :
    try:
        if produto_id is None or produto_id <= 0:
            raise HTTPException(status_code=400, detail="ID do produto inválido.")
        
        db_produto = await engine.find_one(Produto, Produto.id == produto_id)
        if not db_produto:
            raise HTTPException(status_code=404, detail="Produto não encontrado")
        
        produto_data = produto_atualizado.model_dump(exclude_unset=True, exclude='id')
        db_produto.model_update(produto_data, exclude_unset=True)
        await engine.save(db_produto)
        return {"message": "Produto atualizado com sucesso"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao remover produto: {str(e)}")

@router.delete("/{produto_id}", description="Remove um produto do sistema.")
async def deletar_produto(produto_id: ObjectId):
    try:
        if produto_id is None or produto_id <= 0:
            raise HTTPException(status_code=400, detail="ID do produto inválido.")
        
        produto = await engine.find_one(Produto, Produto.id == produto_id)
        if not produto:
            raise HTTPException(status_code=404, detail="Produto não encontrado")
        
        await engine.delete(produto)
        return {"message": "Produto removido com sucesso"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao remover produto: {str(e)}")

@router.get("/quantidade/", description="Retorna a quantidade total de produtos cadastrados.")
async def quantidade_produtos():
    try:
        return {"Quantidade": await engine.count(Produto)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao contar produtos: {str(e)}")


@router.get("/categoria_qtd/{categoria}", description="Retorna a quantidade de produtos por categoria.")
async def quantidade_produtos(categoria: str):
    try:
        return {"Quantidade": await engine.count(Produto, query.eq(Produto.categoria, categoria))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao contar produtos por categoria: {str(e)}")
    
@router.get("/preco_maior_que/{preco}", description="Lista produtos com preço maior que o valor especificado")
async def listar_produtos_por_preco(preco: float) -> list[Produto]:
    try:
        return await engine.find(Produto, query.gte(Produto.preco, preco))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na busca: {str(e)}")

@router.get("/{produto_id}/disponibilidade")
async def verificar_disponibilidade(produto_id: ObjectId, quantidade: int):
    try:
        produto = await engine.find_one(Produto, Produto.id == produto_id)
        if not produto:
            raise HTTPException(status_code=404, detail="Produto não encontrado")
        
        disponivel = produto.estoque >= quantidade
        return {
            "produto_id": produto_id,
            "estoque_atual": produto.estoque,
            "quantidade_solicitada": quantidade,
            "disponivel": disponivel
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao verificar disponibilidade: {str(e)}")
    