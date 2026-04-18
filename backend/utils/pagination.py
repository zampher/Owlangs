"""
Generic pagination utilities for API endpoints.
Provides reusable pagination parameters, response structures, and helper functions.
"""
from typing import List, Optional, TypeVar, Generic, Dict, Any
from dataclasses import dataclass
from fastapi import Query

# Import pagination configuration
try:
    from app.config.pagination_config import MAX_PAGINATION_LIMIT, DEFAULT_PAGINATION_LIMIT
except ImportError:
    # Fallback values if config module is not available
    MAX_PAGINATION_LIMIT = 100000
    DEFAULT_PAGINATION_LIMIT = 200

T = TypeVar('T')


@dataclass
class PaginationParams:
    """Pagination parameters with validation."""
    offset: int
    limit: int
    max_limit: int = MAX_PAGINATION_LIMIT
    default_limit: int = DEFAULT_PAGINATION_LIMIT
    
    def __post_init__(self):
        """Validate and clamp pagination parameters."""
        # Ensure offset is non-negative
        self.offset = max(0, self.offset)
        # Clamp limit to valid range
        self.limit = max(1, min(self.limit, self.max_limit))
    
    @property
    def page(self) -> int:
        """Calculate current page number (1-based)."""
        return (self.offset // self.limit) + 1 if self.limit > 0 else 1
    
    @property
    def page_size(self) -> int:
        """Alias for limit."""
        return self.limit


@dataclass
class PaginatedResponse(Generic[T]):
    """Generic paginated response structure."""
    items: List[T]
    offset: int
    limit: int
    total: int
    page: Optional[int] = None
    page_size: Optional[int] = None
    has_prev: Optional[bool] = None
    has_next: Optional[bool] = None
    
    def __post_init__(self):
        """Calculate derived fields if not provided."""
        if self.page is None:
            self.page = (self.offset // self.limit) + 1 if self.limit > 0 else 1
        if self.page_size is None:
            self.page_size = self.limit
        if self.has_prev is None:
            self.has_prev = self.offset > 0
        if self.has_next is None:
            self.has_next = (self.offset + self.limit) < self.total
    
    def to_dict(self, **extra_fields) -> Dict[str, Any]:
        """Convert to dictionary for JSON response."""
        result = {
            "items": self.items,
            "offset": self.offset,
            "limit": self.limit,
            "total": self.total,
            "page": self.page,
            "page_size": self.page_size,
            "has_prev": self.has_prev,
            "has_next": self.has_next,
        }
        result.update(extra_fields)
        return result


def parse_pagination_params(
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(DEFAULT_PAGINATION_LIMIT, ge=1, le=MAX_PAGINATION_LIMIT, description="Maximum number of items to return"),
    max_limit: int = MAX_PAGINATION_LIMIT,
    default_limit: int = DEFAULT_PAGINATION_LIMIT,
) -> PaginationParams:
    """
    Parse pagination parameters from FastAPI query parameters.
    
    Args:
        offset: Number of items to skip
        limit: Maximum number of items to return
        max_limit: Maximum allowed limit (for validation)
        default_limit: Default limit if not provided
    
    Returns:
        PaginationParams instance with validated values
    """
    return PaginationParams(
        offset=offset,
        limit=limit if limit > 0 else default_limit,
        max_limit=max_limit,
        default_limit=default_limit,
    )


def paginate_items(
    items: List[T],
    params: PaginationParams,
) -> PaginatedResponse[T]:
    """
    Paginate a list of items.
    
    Args:
        items: Full list of items to paginate
        params: Pagination parameters
    
    Returns:
        PaginatedResponse with paginated items
    """
    total = len(items)
    # Clamp offset to valid range
    offset = min(params.offset, max(0, total - 1)) if total > 0 else 0
    end = min(offset + params.limit, total)
    paginated_items = items[offset:end]
    
    return PaginatedResponse(
        items=paginated_items,
        offset=offset,
        limit=params.limit,
        total=total,
    )


def get_segment_slice(
    segments: List[str],
    offset: int,
    limit: int,
) -> tuple[List[str], int]:
    """
    Get a slice of segments with validation.
    
    Args:
        segments: Full list of segments
        offset: Starting index
        limit: Maximum number of segments to return
    
    Returns:
        Tuple of (segments_slice, total_count)
    """
    total = len(segments)
    # Clamp offset to valid range
    offset = min(offset, max(0, total - 1)) if total > 0 else 0
    end = min(offset + limit, total)
    return segments[offset:end], total

