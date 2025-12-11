"""
Itinerary service for itinerary CRUD and status operations.
"""
from typing import Optional, TYPE_CHECKING

from sqlmodel import Session

from database.repository import (
    TravelItineraryRepository,
    ChatMessageRepository,
    ItineraryNotFoundError,
    VersionConflictError,
    InvalidStatusTransitionError,
)
from database.models import Itinerary
from api.schemas import (
    ItineraryResponse,
    ItineraryListResponse,
    ItineraryStatusResponse,
    ItineraryDeleteResponse,
    ItineraryUpdateRequest,
    ChatHistoryResponse,
)
from agents.orchestration import Orchestrator
from utils.logger import get_logger
from api.utils import itinerary_to_response

if TYPE_CHECKING:
    from api.context import TravelContext

logger = get_logger()


class ItineraryService:
    """Service for itinerary operations."""
    
    def __init__(self, session: Session):
        """
        Initialize itinerary service.
        
        Args:
            session: Database session
        """
        self.session = session
        self.repo = TravelItineraryRepository(session)
        self.chat_repo = ChatMessageRepository(session)
    
    def create_itinerary(
        self,
        traveler_id: str,
        original_query: Optional[str] = None,
    ) -> ItineraryResponse:
        """
        Create a new draft itinerary.
        
        Args:
            traveler_id: Traveler identifier
            original_query: Original NL query
        
        Returns:
            ItineraryResponse with created itinerary
        """
        logger.info(f"Creating itinerary for traveler_id={traveler_id}")
        
        itinerary = self.repo.create(
            traveler_id=traveler_id,
            original_query=original_query,
        )
        
        logger.info(f"Created itinerary id={itinerary.id}")
        return itinerary_to_response(itinerary)
    
    def get_itinerary(self, itinerary_id: str) -> ItineraryResponse:
        """
        Get itinerary by ID.
        
        Args:
            itinerary_id: Itinerary identifier
        
        Returns:
            ItineraryResponse with itinerary data
        
        Raises:
            ItineraryNotFoundError: If itinerary doesn't exist
        """
        logger.debug(f"Getting itinerary id={itinerary_id}")
        
        itinerary = self.repo.get_by_id_or_raise(itinerary_id)
        logger.debug(f"Found itinerary id={itinerary_id}, status={itinerary.status}")
        return itinerary_to_response(itinerary)
    
    def list_itineraries(
        self,
        status: Optional[str] = None,
        traveler_id: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> ItineraryListResponse:
        """
        List itineraries with optional filtering and pagination.
        
        Args:
            status: Filter by status (draft, confirmed, cancelled)
            traveler_id: Filter by traveler ID
            page: Page number (1-indexed)
            limit: Items per page
        
        Returns:
            ItineraryListResponse with paginated results
        """
        logger.debug(f"Listing itineraries: status={status}, traveler_id={traveler_id}, page={page}, limit={limit}")
        
        itineraries, total = self.repo.list_all(
            status=status,
            traveler_id=traveler_id,
            page=page,
            limit=limit,
        )
        
        logger.info(f"Listed itineraries: returned {len(itineraries)} of {total} total")
        
        return ItineraryListResponse(
            items=[itinerary_to_response(it) for it in itineraries],
            total=total,
            page=page,
            limit=limit,
            has_more=(page * limit) < total,
        )
    
    def update_itinerary(
        self,
        itinerary_id: str,
        request: ItineraryUpdateRequest,
    ) -> ItineraryResponse:
        """
        Update itinerary with optimistic locking.
        
        Only updates fields that were explicitly provided in the request.
        Uses model_fields_set to detect which fields were set.
        
        Args:
            itinerary_id: Itinerary identifier
            request: ItineraryUpdateRequest with update data
        
        Returns:
            ItineraryResponse with updated itinerary
        
        Raises:
            ItineraryNotFoundError: If itinerary doesn't exist
            VersionConflictError: If version doesn't match
            InvalidStatusTransitionError: If itinerary is not in draft status
        """
        logger.info(f"Updating itinerary id={itinerary_id}, version={request.version}")
        
        # Build update kwargs - use ... as sentinel for "not provided"
        kwargs = {
            "itinerary_id": itinerary_id,
            "version": request.version,
        }
        
        # Only include fields that were explicitly provided in request
        if request.flight_reservation is not None or "flight_reservation" in request.model_fields_set:
            kwargs["flight_reservation"] = request.flight_reservation
        if request.hotel_reservation is not None or "hotel_reservation" in request.model_fields_set:
            kwargs["hotel_reservation"] = request.hotel_reservation
        if request.car_reservation is not None or "car_reservation" in request.model_fields_set:
            kwargs["car_reservation"] = request.car_reservation
        
        logger.debug(f"Update fields: {list(kwargs.keys())}")
        
        itinerary = self.repo.update(**kwargs)
        logger.info(f"Updated itinerary id={itinerary_id}, new_version={itinerary.version}")
        return itinerary_to_response(itinerary)
    
    def delete_itinerary(self, itinerary_id: str) -> ItineraryDeleteResponse:
        """
        Delete a draft itinerary.
        
        Args:
            itinerary_id: Itinerary identifier
        
        Returns:
            ItineraryDeleteResponse with deletion result
        
        Raises:
            ItineraryNotFoundError: If itinerary doesn't exist
            InvalidStatusTransitionError: If itinerary is not in draft status
        """
        logger.info(f"Deleting itinerary id={itinerary_id}")
        
        self.repo.delete(itinerary_id)
        logger.info(f"Deleted itinerary id={itinerary_id}")
        
        return ItineraryDeleteResponse(
            success=True,
            message=f"Itinerary {itinerary_id} deleted successfully"
        )
    
    def confirm_itinerary(
        self,
        itinerary_id: str,
        orchestrator: Orchestrator,
        ctx: "TravelContext",
    ) -> ItineraryStatusResponse:
        """
        Confirm a draft itinerary (locks from further edits).
        
        Args:
            itinerary_id: Itinerary identifier
            orchestrator: Orchestrator instance for status transition
            ctx: TravelContext with session
        
        Returns:
            ItineraryStatusResponse with confirmation result
        
        Raises:
            ItineraryNotFoundError: If itinerary doesn't exist
            InvalidStatusTransitionError: If itinerary is not in draft status
        """
        logger.info(f"Confirming itinerary id={itinerary_id}")
        
        # Set up context
        ctx.itinerary_id = itinerary_id
        
        itinerary = orchestrator.confirm_itinerary(ctx)
        logger.info(f"Confirmed itinerary id={itinerary_id}")
        
        return ItineraryStatusResponse(
            id=itinerary.id,
            status=itinerary.status,
            message="Itinerary confirmed successfully"
        )
    
    def cancel_itinerary(
        self,
        itinerary_id: str,
        orchestrator: Orchestrator,
        ctx: "TravelContext",
    ) -> ItineraryStatusResponse:
        """
        Cancel an itinerary (draft or confirmed).
        
        Args:
            itinerary_id: Itinerary identifier
            orchestrator: Orchestrator instance for status transition
            ctx: TravelContext with session
        
        Returns:
            ItineraryStatusResponse with cancellation result
        
        Raises:
            ItineraryNotFoundError: If itinerary doesn't exist
            InvalidStatusTransitionError: If itinerary is already cancelled
        """
        logger.info(f"Cancelling itinerary id={itinerary_id}")
        
        # Set up context
        ctx.itinerary_id = itinerary_id
        
        itinerary = orchestrator.cancel_itinerary(ctx)
        logger.info(f"Cancelled itinerary id={itinerary_id}")
        
        return ItineraryStatusResponse(
            id=itinerary.id,
            status=itinerary.status,
            message="Itinerary cancelled successfully",
            cancelled_at=itinerary.cancelled_at
        )
    
    def get_chat_history(
        self,
        itinerary_id: str,
        limit: int = 20,
    ) -> ChatHistoryResponse:
        """
        Get chat history for an itinerary.
        
        Args:
            itinerary_id: Itinerary identifier
            limit: Number of messages to return
        
        Returns:
            ChatHistoryResponse with chat messages
        
        Raises:
            ItineraryNotFoundError: If itinerary doesn't exist
        """
        logger.debug(f"Getting history for itinerary id={itinerary_id}")
        
        # Check if itinerary exists first
        if not self.repo.get_by_id(itinerary_id):
            raise ItineraryNotFoundError(itinerary_id)
        
        messages = self.chat_repo.get_history(itinerary_id, limit=limit)
        
        return ChatHistoryResponse(
            itinerary_id=itinerary_id,
            messages=messages
        )
