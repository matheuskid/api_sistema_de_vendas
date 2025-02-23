from fastapi import APIRouter, HTTPException, Query, Depends
from Models.models import Cliente, ClienteAtualizado, PaginatedResponse
from typing import List
from Context.database import engine
from odmantic import ObjectId, query

router = APIRouter(prefix="/clientes", tags=["Clientes"])

@router.post("/", response_model=Cliente, description="Insere um novo cliente no sistema.")
async def inserir_cliente(cliente: Cliente) -> Cliente:
    try:
        await engine.save(cliente)
        return cliente
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao criar cliente: {str(e)}")

@router.get("/", response_model=PaginatedResponse[Cliente], description="Lista todos os clientes com paginação")
async def listar_clientes(
    page: int = Query(default=1, ge=1, description="Número da página"),
    size: int = Query(default=10, ge=1, le=100, description="Itens por página"),
) -> PaginatedResponse[Cliente]:
    try:
        # Calcula o offset
        offset = (page - 1) * size
        
        # Busca total de registros
        total = await engine.count(Cliente)
        
        # Busca items da página atual
        items = await engine.find(Cliente, skip=offset, limit=size)
        
        # Calcula total de páginas
        pages = -(-total // size)  # Divisão arredondada para cima
        
        # Cria resposta
        response = PaginatedResponse(
            items=items,
            total=total,
            page=page,
            size=size,
            pages=pages
        )
        
        return response
    
    except Exception as e:
        print(f"Erro ao listar clientes: {e}")  # Debug
        raise HTTPException(status_code=500, detail=f"Erro ao listar clientes: {str(e)}")
    
@router.get("/{cliente_id}", response_model=Cliente, description="Retorna um cliente existente.")
async def listar_clientes(cliente_id: ObjectId) -> Cliente:
    try:
        if cliente_id is None:
            raise HTTPException(status_code=400, detail="ID do cliente inválido.")
        
        cliente = await engine.find_one(Cliente, Cliente.id == cliente_id)

        if not cliente:
            raise HTTPException(status_code=404, detail="Cliente não encontrado")
        
        return cliente
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar clientes: {str(e)}")

@router.put("/{cliente_id}", description="Atualiza as informações de um cliente existente.")
async def atualizar_cliente(cliente_id: ObjectId, cliente_atualizado: ClienteAtualizado):
    try:
        if cliente_id is None:
            raise HTTPException(status_code=400, detail="ID do cliente inválido.")
        
        db_cliente = await engine.find_one(Cliente, Cliente.id == cliente_id)
        if not db_cliente:
            raise HTTPException(status_code=404, detail="Cliente não encontrado")
        
        cliente_data = cliente_atualizado.model_dump(exclude_unset=True, exclude='id')
        db_cliente.model_update(cliente_data, exclude_unset=True)
        await engine.save(db_cliente)
        return {"message": "Cliente atualizado com sucesso"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar cliente: {str(e)}")

@router.delete("/{cliente_id}", description="Remove um cliente do sistema.")
async def deletar_cliente(cliente_id: ObjectId):
    try:
        if cliente_id is None:
            raise HTTPException(status_code=400, detail="ID do cliente inválido.")
        
        cliente = await engine.find_one(Cliente, Cliente.id == cliente_id)
        if not cliente:
            raise HTTPException(status_code=404, detail="Cliente não encontrado")
        
        await engine.delete(cliente)
        return {"message": "Cliente removido com sucesso"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao remover cliente: {str(e)}")

@router.get("/quantidade/", description="Retorna a quantidade total de clientes cadastrados.")
async def quantidade_clientes():
    try:
        return {"Quantidade": await engine.count(Cliente)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao contar clientes: {str(e)}")

@router.get("/clientes_por_estado/{estado}", description="Retorna clientes por estado.")
async def quantidade_clientes(estado: str) -> list[Cliente]:
    try:
        return await engine.find(Cliente, Cliente.estado == estado)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao retornar clientes: {str(e)}")

@router.get("/busca/{nome}", response_model=List[Cliente], description="Busca clientes por nome parcial")
async def buscar_clientes_por_nome(nome: str) -> list[Cliente]:
    try:
        return await engine.find(Cliente, query.match(Cliente.nome, r""+nome))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na busca: {str(e)}")

@router.get("/busca-avancada/", response_model=List[Cliente], description="Busca clientes por texto parcial em múltiplos campos")
async def buscar_clientes_avancado(
    termo: str = Query(..., description="Termo para busca (nome, email, cidade ou estado)"),
    campos: List[str] = Query(
        default=["nome", "email", "cidade", "estado"],
        description="Campos para realizar a busca"
    )
) -> List[Cliente]:
    try:
        # Cria uma lista de condições para cada campo
        condicoes = []
        for campo in campos:
            if hasattr(Cliente, campo):
                # Usa regex para busca parcial case insensitive
                condicoes.append(
                    query.match(getattr(Cliente, campo), f"(?i){termo}")
                )
        
        # Combina as condições com OR
        if condicoes:
            resultado = await engine.find(Cliente, query.or_(*condicoes))
            return resultado
        else:
            return []
            
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Erro na busca avançada: {str(e)}"
        )
