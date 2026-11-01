"""Chapter 4 feature definitions for the isolated local Docker services."""
from datetime import timedelta
from feast import Entity, FeatureView, Field, FileSource, ValueType
from feast.types import String

user = Entity(name="user_id", join_keys=["user_id"], value_type=ValueType.STRING)


def view(name, filename, columns):
    return FeatureView(
        name=name,
        entities=[user],
        ttl=timedelta(days=365),
        schema=[Field(name=column, dtype=String) for column in columns],
        source=FileSource(
            path=f"s3://feature-data-sets/{filename}",
            timestamp_field="feature_timestamp",
            s3_endpoint_override="http://127.0.0.1:19000",
        ),
    )


demographic = view("demographic", "demographic_features.parquet", ["Native_country", "Sex", "Race"])
relationship = view("relationship", "relationship_features.parquet", ["Relationship", "Marital-Status"])
occupation = view("occupation", "occupational_features.parquet", ["Workclass", "Education", "Occupation"])
