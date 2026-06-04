from openscire.references.indexing.filters import (
    AndFilter,
    FieldFilter,
    FilterOperator,
    NotFilter,
    OrFilter,
    and_,
    evaluate,
    field,
    not_,
    or_,
)


class TestFieldFilter:
    def test_eq(self):
        f = FieldFilter("year", FilterOperator.eq, 2024)
        assert f.evaluate({"year": 2024}) is True
        assert f.evaluate({"year": 2023}) is False

    def test_neq(self):
        f = FieldFilter("year", FilterOperator.neq, 2024)
        assert f.evaluate({"year": 2023}) is True
        assert f.evaluate({"year": 2024}) is False

    def test_gt(self):
        f = FieldFilter("year", FilterOperator.gt, 2020)
        assert f.evaluate({"year": 2024}) is True
        assert f.evaluate({"year": 2020}) is False

    def test_gte(self):
        f = FieldFilter("year", FilterOperator.gte, 2020)
        assert f.evaluate({"year": 2020}) is True
        assert f.evaluate({"year": 2019}) is False

    def test_lt(self):
        f = FieldFilter("year", FilterOperator.lt, 2020)
        assert f.evaluate({"year": 2019}) is True
        assert f.evaluate({"year": 2020}) is False

    def test_lte(self):
        f = FieldFilter("year", FilterOperator.lte, 2020)
        assert f.evaluate({"year": 2020}) is True
        assert f.evaluate({"year": 2021}) is False

    def test_in(self):
        f = FieldFilter("source", FilterOperator.in_, ["pubmed", "arxiv"])
        assert f.evaluate({"source": "pubmed"}) is True
        assert f.evaluate({"source": "zotero"}) is False

    def test_contains(self):
        f = FieldFilter("journal", FilterOperator.contains, "Nature")
        assert f.evaluate({"journal": "Nature Communications"}) is True
        assert f.evaluate({"journal": "Science"}) is False

    def test_none_field(self):
        f = FieldFilter("year", FilterOperator.eq, 2024)
        assert f.evaluate({}) is False

    def test_none_field_neq(self):
        f = FieldFilter("year", FilterOperator.neq, 2024)
        assert f.evaluate({}) is True


class TestCompositeFilters:
    def test_and(self):
        f = AndFilter(
            FieldFilter("year", FilterOperator.gte, 2020),
            FieldFilter("source", FilterOperator.eq, "pubmed"),
        )
        assert f.evaluate({"year": 2024, "source": "pubmed"}) is True
        assert f.evaluate({"year": 2024, "source": "arxiv"}) is False
        assert f.evaluate({"year": 2019, "source": "pubmed"}) is False

    def test_or(self):
        f = OrFilter(
            FieldFilter("year", FilterOperator.eq, 2024),
            FieldFilter("source", FilterOperator.eq, "pubmed"),
        )
        assert f.evaluate({"year": 2024, "source": "arxiv"}) is True
        assert f.evaluate({"year": 2023, "source": "pubmed"}) is True
        assert f.evaluate({"year": 2023, "source": "arxiv"}) is False

    def test_not(self):
        f = NotFilter(FieldFilter("year", FilterOperator.eq, 2024))
        assert f.evaluate({"year": 2023}) is True
        assert f.evaluate({"year": 2024}) is False

    def test_nested(self):
        f = AndFilter(
            FieldFilter("year", FilterOperator.gte, 2020),
            OrFilter(
                FieldFilter("source", FilterOperator.eq, "pubmed"),
                FieldFilter("journal", FilterOperator.contains, "Nature"),
            ),
        )
        assert f.evaluate({"year": 2024, "source": "pubmed", "journal": "Science"}) is True
        assert f.evaluate({"year": 2024, "source": "arxiv", "journal": "Nature Comms"}) is True
        assert f.evaluate({"year": 2024, "source": "arxiv", "journal": "Science"}) is False
        assert f.evaluate({"year": 2019, "source": "pubmed", "journal": "Nature"}) is False


class TestHelperFunctions:
    def test_field(self):
        f = field("year", "eq", 2024)
        assert isinstance(f, FieldFilter)
        assert f.evaluate({"year": 2024}) is True

    def test_and_(self):
        f = and_(
            field("year", "gte", 2020),
            field("source", "eq", "pubmed"),
        )
        assert isinstance(f, AndFilter)
        assert f.evaluate({"year": 2024, "source": "pubmed"}) is True

    def test_or_(self):
        f = or_(
            field("year", "eq", 2024),
            field("source", "eq", "pubmed"),
        )
        assert isinstance(f, OrFilter)

    def test_not_(self):
        f = not_(field("year", "eq", 2024))
        assert isinstance(f, NotFilter)

    def test_evaluate_none(self):
        assert evaluate(None, {"year": 2024}) is True
        assert evaluate(field("year", "eq", 2024), {"year": 2024}) is True
