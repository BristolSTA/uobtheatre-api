if echo 0 | tail -1 | grep 1
then
  echo "No users"
else
  echo "users"
fi
