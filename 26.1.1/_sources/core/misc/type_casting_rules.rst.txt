:orphan:

.. csv-table::
   :header: "From \ To", "String", "Number", "Integer", "Object", "Array", "Boolean", "Null"

   "**String**", "✅", "❌", "❌", "❌", "❌", "❌", "❌"
   "**Number**", "✅ json.dumps(value)", "✅", "✅ decimals truncated", "❌", "❌", "✅ value != 0", "❌"
   "**Integer**", "✅ json.dumps(value)", "✅", "✅", "❌", "❌", "✅ value != 0", "❌"
   "**Object**", "✅ json.dumps(value)", "❌", "❌", "✅", "❌", "❌", "❌"
   "**Array**", "✅ json.dumps(value)", "❌", "❌", "❌", "✅", "❌", "❌"
   "**Boolean**", "✅ json.dumps(value)", "✅ 1 if value else 0", "✅ 1 if value else 0", "❌", "❌", "✅", "❌"
   "**Null**", "✅ empty string", "❌", "❌", "❌", "❌", "❌", "✅"
