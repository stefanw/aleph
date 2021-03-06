
var loadSearch = ['$http', '$q', '$route', '$location', 'Query', 'Session', 'Metadata',
    function($http, $q, $route, $location, Query, Session, Metadata) {
  var dfd = $q.defer();

  Metadata.get().then(function(metadata) {
    Session.get().then(function(session) {
      var query = angular.copy(Query.load());
      query['limit'] = 30;
      query['snippet'] = 140;
      query['offset'] = $location.search().offset || 0;
      Query.setLastSearch($location.search());
      $http.get('/api/1/query', {cache: true, params: query}).then(function(res) {
        var result = res.data;
        dfd.resolve({
          'result': result,
          'metadata': metadata
        });
      }, function(err) {
        if (err.status == 400) {
          dfd.resolve({
            'result': {
              'error': err.data
            },
            'metadata': metadata
          });
        }
        dfd.reject(err);  
      });
    }, function(err) {
      dfd.reject(err);
    });
  }, function(err) {
    dfd.reject(err);
  });

  return dfd.promise;
}];
