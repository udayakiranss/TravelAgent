"""
Agent/LLM operation routes for natural language planning and modification.
"""
from fastapi import APIRouter, Depends, HTTPException, status

from api.schemas import (
    NaturalLanguageQueryRequest,
    NaturalLanguageModifyRequest,
    PlanResponse,
    ModifyResponse,
)
from api.context import TravelContext
from api.dependencies import (
    get_context,
    get_orchestrator,
    get_planner,
    get_planning_service,
    get_conversation_service,
)
from api.services.conversation_service import ConversationService
from api.services.planning_service import PlanningService
from agents.orchestration import Orchestrator
from agents.planning import TravelPlanner
from database.repository import (
    ItineraryNotFoundError,
    LLMUnavailableError,
    InvalidStatusTransitionError,
)
from api.utils import itinerary_to_response, create_error_response, handle_domain_exception
from utils.logger import get_logger

logger = get_logger()

router = APIRouter(tags=["Agent"])


@router.post(
    "/agent/plan",
    response_model=PlanResponse,
    summary="Plan trip",
    description="Generate travel options, auto-select best option, and create draft itinerary"
)
def plan_trip(
    request: NaturalLanguageQueryRequest,
    ctx: TravelContext = Depends(get_context),
    service: PlanningService = Depends(get_planning_service),
):
    """
    Plan a trip from natural language query.
    
    Thin route that delegates to PlanningService.
    """
    try:
        return service.plan_trip(request, ctx)
    except LLMUnavailableError as e:
        handle_domain_exception(e)
    except Exception as e:
        logger.error(f"Plan trip failed: {type(e).__name__}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response(
                "PLANNING_ERROR",
                f"Error during trip planning: {str(e)}",
                500
            )
        )


@router.post(
    "/itineraries/{itinerary_id}/modify",
    response_model=ModifyResponse,
    summary="Modify via NL",
    description="Modify itinerary via natural language instruction"
)
def modify_itinerary_nl(
    itinerary_id: str,
    request: NaturalLanguageModifyRequest,
    ctx: TravelContext = Depends(get_context),
    orchestrator: Orchestrator = Depends(get_orchestrator),
    conversation_service: ConversationService = Depends(get_conversation_service),
):
    """
    Modify an itinerary using natural language instructions.
    
    Loads conversation context into TravelContext, then delegates to Orchestrator.
    """
    logger.info(f"Modify itinerary request: id={itinerary_id}, instruction='{request.instruction[:50]}...'" if len(request.instruction) > 50 else f"Modify itinerary request: id={itinerary_id}, instruction='{request.instruction}'")
    
    # Populate context from request
    ctx.traveler_id = request.traveler_id
    ctx.itinerary_id = itinerary_id
    
    try:
        # Load conversation state using service
        conversation_service.load_conversation_state(itinerary_id, ctx)
        
        # Delegate to orchestrator (thin route)
        result = orchestrator.modify_itinerary(request.instruction, ctx)
        
        # Save chat messages using service
        conversation_service.save_chat_message(itinerary_id, "user", request.instruction)
        if result.get("message"):
            conversation_service.save_chat_message(itinerary_id, "assistant", result["message"])
        
        logger.info(f"Modification processed for itinerary id={itinerary_id}")
        
        return ModifyResponse(
            success=result["success"],
            updated_itinerary=itinerary_to_response(result["updated_itinerary"]) if result.get("updated_itinerary") else None,
            message=result["message"],
            partial=result.get("partial", False)
        )
        
    except (ItineraryNotFoundError, LLMUnavailableError) as e:
        handle_domain_exception(e)
    except InvalidStatusTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                "CANNOT_MODIFY_CONFIRMED",
                f"Cannot modify itinerary in '{e.current_status}' status",
                400
            )
        )
    except Exception as e:
        logger.error(f"Modification failed for itinerary id={itinerary_id}: {type(e).__name__}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response(
                "MODIFICATION_ERROR",
                f"Error during modification: {str(e)}",
                500
            )
        )
