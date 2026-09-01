from google.cloud.firestore import Increment

class FakeDocumentSnapshot:
    def __init__(self, doc_id: str, data: dict = None, exists: bool = True, collection = None):
        self.id = doc_id
        self._data = dict(data) if data is not None else None
        self.exists = exists
        self._collection = collection

    def to_dict(self):
        return dict(self._data) if self._data else {}

    @property
    def reference(self):
        if self._collection is not None:
            return self._collection.document(self.id)
        return self

    def delete(self):
        if self._collection is not None:
            self._collection.document(self.id).delete()


class FakeQuery:
    def __init__(self, collection, filters=None, orders=None, limit_val=None, start_after_doc=None, offset_val=None):
        self.collection = collection
        self.filters = filters or []
        self.orders = orders or []
        self.limit_val = limit_val
        self.start_after_doc = start_after_doc
        self.offset_val = offset_val

    def where(self, field, op, val):
        new_filters = list(self.filters)
        new_filters.append((field, op, val))
        return FakeQuery(self.collection, new_filters, self.orders, self.limit_val, self.start_after_doc, self.offset_val)

    def order_by(self, field, direction="ASCENDING"):
        new_orders = list(self.orders)
        new_orders.append((field, direction))
        return FakeQuery(self.collection, self.filters, new_orders, self.limit_val, self.start_after_doc, self.offset_val)

    def limit(self, n):
        return FakeQuery(self.collection, self.filters, self.orders, n, self.start_after_doc, self.offset_val)

    def offset(self, n):
        return FakeQuery(self.collection, self.filters, self.orders, self.limit_val, self.start_after_doc, n)

    def start_after(self, doc):
        return FakeQuery(self.collection, self.filters, self.orders, self.limit_val, doc, self.offset_val)

    def stream(self):
        docs = list(self.collection._docs.values())
        filtered = []
        for d in docs:
            match = True
            for field, op, val in self.filters:
                doc_val = d.get(field)
                if op == "==" and doc_val != val:
                    match = False
                    break
                elif op == "!=" and doc_val == val:
                    match = False
                    break
            if match:
                filtered.append(d)

        for field, direction in self.orders:
            reverse = direction.upper() == "DESCENDING"
            filtered.sort(key=lambda x: str(x.get(field, "")), reverse=reverse)

        if self.start_after_doc:
            target_id = self.start_after_doc.id if hasattr(self.start_after_doc, "id") else str(self.start_after_doc)
            found_idx = -1
            for i, d in enumerate(filtered):
                if d.get("id") == target_id:
                    found_idx = i
                    break
            if found_idx != -1:
                filtered = filtered[found_idx + 1 :]
        elif self.offset_val:
            filtered = filtered[self.offset_val :]

        if self.limit_val is not None:
            filtered = filtered[: self.limit_val]

        return [FakeDocumentSnapshot(d.get("id", ""), d, True, collection=self.collection) for d in filtered]


class FakeDocRef:
    def __init__(self, doc_id: str, collection):
        self.id = doc_id
        self.collection = collection

    @property
    def reference(self):
        return self

    def set(self, data: dict, merge: bool = False):
        if merge and self.id in self.collection._docs:
            existing = self.collection._docs[self.id]
            for k, v in data.items():
                if isinstance(v, Increment):
                    existing[k] = existing.get(k, 0) + v.value
                else:
                    existing[k] = v
        else:
            final_data = dict(data)
            for k, v in list(final_data.items()):
                if isinstance(v, Increment):
                    final_data[k] = v.value
            final_data["id"] = self.id
            self.collection._docs[self.id] = final_data

    def get(self):
        if self.id in self.collection._docs:
            return FakeDocumentSnapshot(self.id, self.collection._docs[self.id], True)
        return FakeDocumentSnapshot(self.id, None, False)

    def update(self, data: dict):
        if self.id not in self.collection._docs:
            raise KeyError(f"Document {self.id} does not exist")
        doc = self.collection._docs[self.id]
        for k, v in data.items():
            if isinstance(v, Increment):
                doc[k] = doc.get(k, 0) + v.value
            else:
                doc[k] = v

    def delete(self):
        if self.id in self.collection._docs:
            del self.collection._docs[self.id]


class FakeCollection:
    def __init__(self, name: str):
        self.name = name
        self._docs = {}

    def document(self, doc_id: str):
        return FakeDocRef(doc_id, self)

    def where(self, field, op, val):
        return FakeQuery(self).where(field, op, val)

    def order_by(self, field, direction="ASCENDING"):
        return FakeQuery(self).order_by(field, direction)

    def limit(self, n):
        return FakeQuery(self).limit(n)

    def offset(self, n):
        return FakeQuery(self).offset(n)

    def start_after(self, doc):
        return FakeQuery(self).start_after(doc)

    def stream(self):
        return FakeQuery(self).stream()


class FakeBatch:
    def __init__(self):
        self.actions = []

    def set(self, doc_ref, data, merge=False):
        self.actions.append(lambda: doc_ref.set(data, merge=merge))

    def update(self, doc_ref, data):
        self.actions.append(lambda: doc_ref.update(data))

    def delete(self, doc_ref):
        target = getattr(doc_ref, "reference", doc_ref)
        self.actions.append(lambda: target.delete())

    def commit(self):
        for act in self.actions:
            act()
        self.actions.clear()


class FakeFirestoreClient:
    def __init__(self):
        self._collections = {}

    def collection(self, name: str):
        if name not in self._collections:
            self._collections[name] = FakeCollection(name)
        return self._collections[name]

    def batch(self):
        return FakeBatch()
