def format_title(t):
  """ Format a bibtex title in a html title """

  # Lower case except parts between {} (does not support nested {})
  i = 1
  j = t.find("{",i)
  while j != -1:
    # i...j{...k}...
    k = t.find("}",j)
    if k == -1:
      # error
      break
    t = t[:i] + t[i:j].lower() + t[j+1:k] + t[k+1:]
    i = k
    j = t.find("{",i)
  if i != -1:
    t = t[:i] + t[i:].lower()
  return t
