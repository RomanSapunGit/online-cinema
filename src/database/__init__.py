import os

from database.models.base import Base
from database.models.order_models import (
    OrderModel,
    OrderItemModel,
    OrderStatusEnum
)
from database.models.movie_models import (
    GenreModel,
    DirectorModel,
    StarModel,
    CertificationModel,
    MovieModel,
    movie_stars,
    MovieRatingModel,
    movie_genres,

)
from database.models.payment_models import (
    PaymentModel,
    PaymentItemModel
)
from database.models.cart_models import (
    CartModel,
    CartItemModel
)
from database.models.user_models import (
    UserModel,
    UserGroupModel,
    UserGroupEnum,
    UserProfileModel
)
from database.models.token_models import (
    TokenBaseModel,
    RefreshTokenModel,
    ActivationTokenModel,
    PasswordResetTokenModel
)
from database.database_sqlite import reset_sqlite_database as reset_database

environment = os.getenv("ENVIRONMENT", "developing")
if environment == "testing":
    from database.database_sqlite import (
        get_sqlite_db_contextmanager as get_db_contextmanager,
        get_sqlite_db as get_db
    )
else:
    from database.database_postgres import (
        get_postgresql_db_contextmanager as get_db_contextmanager,
        get_postgresql_db as get_db
    )
