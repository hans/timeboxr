// global
// variables
// assumed
// here:
// targetDate,
// utcOffset,
// gcalEvents

$(function(){
var calendarEl = $("#calendar");

var getTodos = function() {
  return $("#todos li").map(function(i, el) {
    el = $(el);
    return {
      "id": el.data("id"),
      "content": el.find(".todo-name").text(),
      "predictedTime": parseFloat(el.find(".todo-time-number").text()),
      "project": el.find(".project-name").text(),
    }
  }).get();
}

var getTodoEl = function(id) {
  return $("#todos li[data-id=" + id + "]");
};

var showTodoDelinquent = function(todo, isDelinquent) {
  getTodoEl(todo.id).toggleClass("todo-delinquent", isDelinquent);
};

/*
  * Repack the calendar with the given todo configuration
  * using a 1D bin-packing algorithm.
  */
var repack = function() {
  // Find open bins.
  var startTime = 9 * 60;
  var endTime = 18 * 60;
  var root = {start: startTime, end: endTime};

  // Add gcal events into binary tree.
  // TODO assumes events are sorted by increasing start time, and no overlaps
  var curNode = root;
  $.each(gcalEvents, function(i, ev) {
    var startM = moment(ev.start);
    var endM = moment(ev.end);
    var start = startM.get("hours") * 60 + startM.get("minutes");
    var end = endM.get("hours") * 60 + endM.get("minutes");

    var left = null;
    if (curNode.start < start)
      left = {start: curNode.start, end: start};
    right = {start: end, end: curNode.end};

    curNode.used = true;
    curNode.title = ev.title;
    curNode.start = start;
    curNode.end = end;
    curNode.left = left;
    curNode.right = right;

    // Now walk a step down binary tree.
    curNode = curNode.right;
  });

  var findNode = function(root, duration) {
    if (root == null) {
      return null;
    } else if (root.used) {
      return findNode(root.left, duration) || findNode(root.right, duration);
    } else if (root.end - root.start >= duration) {
      return root;
    } else {
      return null;
    }
  }
  var splitNode = function(node, duration, label, offset) {
    offset = offset || 0;
    if (duration + offset > node.end - node.start) {
      console.error("Duration is too large for node!");
      console.log(node);
      console.log("Duration: " + duration);
      console.log("Offset: " + offset);
    }

    if (offset) {
      node.left = {start: node.start,
              end: node.start + offset};
      node.right = {start: node.start + offset + duration,
              end: node.end};
    } else {
      node.left = null;
      node.right = {start: node.start + duration,
              end: node.end};
    }
    node.used = true;
    node.label = label;
    node.start = node.start + offset;
    node.end = node.start + duration;
    return node;
  }
  var fitBlock = function(duration, label) {
    var node = findNode(root, duration);
    if (node == null) {
      return null;
    }
    return splitNode(node, duration, label);
  }

  // TODO first sort by predicted time
  var todoEvents = getTodos().filter(function(todo) {
    return todo.predictedTime > 0
  }).map(function(todo, i) {
    var node = fitBlock(todo.predictedTime * 60, todo.content);

    // Is the todo delinquent ? (Did it not fit anywhere?)
    var isDelinquent = node == null;
    showTodoDelinquent(todo, isDelinquent);
    if (isDelinquent) {
      console.log("Could not fit todo into day: " + todo.content);
      return null;
    }

    var start = moment(targetDate).add(node.start, "minutes").format();
    var end = moment(targetDate).add(node.end, "minutes").format();
    return {
      id: todo.id,
      title: todo.content,
      start: start,
      end: end,
      editable: true,
      durationEditable: true,
    }
  }).filter(function(todo) { return todo != null });

  return todoEvents;
};

// Instantiate calendar.
var calendar = new FullCalendar.Calendar(calendarEl[0], {
  plugins: [ "timeGrid", "interaction" ],
  defaultView: "timeGridDay",
  defaultDate: targetDate,
  editable: true,
  header: {left: "title", right: ""},
  navLinks: false,

  eventMouseEnter: function(info) {
    if (info.event.source.id == "todoist") {
      getTodoEl(info.event.id).addClass("todo-active");
    }
  },
  eventMouseLeave: function(info) {
    if (info.event.source.id == "todoist") {
      getTodoEl(info.event.id).removeClass("todo-active");
    }
  },
  eventResize: function(info) {
    if (info.event.source.id == "todoist") {
      var duration = moment.duration(moment(info.event.end).diff(moment(info.event.start)));
      var slider = getTodoEl(info.event.id).find(".todo-time")[0].noUiSlider;
      slider.set(duration.asHours());
    }
  },

  eventSources: [
    {
      id: "gcal",
      events: gcalEvents,
      editable: false,
      color: "#ddd",
    },

    {
      id: "todoist",
      events: function(info, successCallback, failureCallback) {
        successCallback(repack());
      },
      editable: true,
    }
  ]
});
calendar.render();
window.calendar = calendar;

// Prepare sliders.
$(".todo-time").map(function(i, el) {
  var numberEl = $(el).find(".todo-time-number")[0];
  var startTime = parseFloat(numberEl.innerText);
  noUiSlider.create(el, {
    start: [startTime],
    step: 15 / 60,
    range: {
      min: [0 / 60],
      max: [360 / 60],
    }
  }).on("update", function(values, handle) {
    numberEl.innerText = values[handle];
    calendar.getEventSourceById("todoist").refetch();
  })
})

var submitButton = $("#btn-submit");
submitButton.click(function() {
  var todoEvents = calendar.getEvents().filter(function(e) {
    return e.source.id == "todoist";
  }).map(function(e) {
    // Remove circular data from event representation so that we can JSONify
    return {
      id: e.id,
      title: e.title,
      start: moment(e.start).format(),
      end: moment(e.end).format(),
    }
  })

  $.ajax({
    url: "/form",
    type: "post",
    contentType: "application/json",
    data: JSON.stringify(todoEvents),
    processData: false,
    success: function(data) {
      console.log(data)
      submitButton.toggleClass("btn-primary btn-outline-success");
    },
    error: function() {
      submitButton.toggleClass("btn-primary btn-outline-danger");
    },
  });

  return false;
})

});
