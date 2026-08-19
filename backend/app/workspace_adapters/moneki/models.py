from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.models import Base


class MonekiStore(Base):
    __tablename__ = "moneki_stores"

    store_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    store_name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(80), index=True)
    district: Mapped[str] = mapped_column(String(120))


class MonekiProduct(Base):
    __tablename__ = "moneki_products"

    product_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    product_name: Mapped[str] = mapped_column(String(120), index=True)
    product_category: Mapped[str] = mapped_column(String(80), index=True)
    unit_price_cents: Mapped[int] = mapped_column(Integer)


class MonekiSale(Base):
    __tablename__ = "moneki_sales"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_moneki_sales_order_id"),
        Index("ix_moneki_sales_date_store", "sale_date", "store_id"),
        Index("ix_moneki_sales_date_product", "sale_date", "product_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    processing_run_id: Mapped[int] = mapped_column(ForeignKey("processing_runs.id"))
    source_row_number: Mapped[int] = mapped_column(Integer)
    order_id: Mapped[str] = mapped_column(String(32))
    sale_date: Mapped[date] = mapped_column(Date)
    store_id: Mapped[str] = mapped_column(ForeignKey("moneki_stores.store_id"))
    product_id: Mapped[str] = mapped_column(ForeignKey("moneki_products.product_id"))
    quantity: Mapped[int] = mapped_column(Integer)
    amount_cents: Mapped[int] = mapped_column(Integer)
    payment_method: Mapped[str] = mapped_column(String(40))
