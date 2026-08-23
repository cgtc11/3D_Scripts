(
	try (CloseRolloutFloater bipedsel_float) catch()
	
	global bs_biped
	global bs_pose_str
--	global bs_biped_rol
	global bipedsel_float

	-- Keep button handlers safe when the rollout was opened before a Biped was
	-- created, or when the previously registered Biped has been deleted.
	fn fn_bs_ensure_biped show_message:true =
	(
		local valid_biped = false
		try
		(
			valid_biped = bs_biped != undefined and isValidNode bs_biped and \
				classof bs_biped.controller == Vertical_Horizontal_Turn
		) catch()

		if not valid_biped and selection.count > 0 do
		(
			try
			(
				if classof selection[1] == Biped_Object do
				(
					bs_biped = biped.getNode selection[1] 13
					valid_biped = bs_biped != undefined
				)
			) catch()
		)

		if not valid_biped do
		(
			for obj in geometry where not valid_biped and classof obj == Biped_Object do
			(
				try
				(
					local root_node = biped.getNode obj 13
					if root_node != undefined and classof root_node.controller == Vertical_Horizontal_Turn do
					(
						bs_biped = root_node
						valid_biped = true
					)
				) catch()
			)
		)

		if not valid_biped and show_message do
			messageBox "Bipedが見つかりません。Bipedを選択するか、+ALLで一覧を更新してください。" title:"Bipedsel"

		valid_biped
	)
	
	fn fn_get_childlen a b =
	(
		append b a
		for c in a.children do b = fn_get_childlen c b
		b
	)
	
	fn fn_sel_obj a b =
	(
		if not (fn_bs_ensure_biped()) do return false
		try
		(
			args = biped.getNode bs_biped a link:b
			if keyboard.altPressed do args = fn_get_childlen args #()
			if keyboard.controlPressed then
			(
				if args.isSelected then (deselect args) else (selectMore args)
			)
			else select args
		) catch()
	)

	fn fn_sel_obj2 a b c =
	(
		if not (fn_bs_ensure_biped()) do return false
		disableSceneRedraw()
		try
		(
			sl = biped.getNode bs_biped a link:b
			fn_sel_obj a b
			local selArr = for i = (b+1) to c collect (biped.getNode bs_biped a link:i)
			if sl.isSelected then (selectMore selArr) else (deselect selArr)
		) catch()
		enableSceneRedraw()
		reDrawViews()
	)

	fn fn_sel_obj3 a bs =
	(
		if not (fn_bs_ensure_biped()) do return false
		disableSceneRedraw()
		try
		(
			sl = biped.getNode bs_biped a link:bs[1]
			fn_sel_obj a bs[1]
			local selArr = for b in bs collect (biped.getNode bs_biped a link:b)
			if sl.isSelected then (selectMore selArr) else (deselect selArr)
		) catch()
		enableSceneRedraw()
		reDrawViews()
	)

	-- -------------------------------------------------------------------------
	-- Build the button images in memory so no external BMP files are required.
	-- -------------------------------------------------------------------------
	fn fn_bs_make_root_bitmap =
	(
		local rows = #(
			"........RRRR........",
			".......RR..RR.......",
			"......RR....RR......",
			".....RR......RR.....",
			"....RR........RR....",
			"...RR..........RR...",
			"..RR............RR..",
			".RR..............RR.",
			"RR................RR",
			"R..................R",
			"R..................R",
			"RR................rR",
			".RR..............rr.",
			"..RR............rr..",
			"...RR..........rr...",
			"....RR........rr....",
			".....RR......rr.....",
			"......RR....rr......",
			".......RR..rr.......",
			"........RRRR........"
		)
		local image = bitmap 20 20 color:(color 255 210 210)

		for y = 1 to rows.count do
		(
			local pixels = for x = 1 to rows[y].count collect
			(
				case (substring rows[y] x 1) of
				(
					"R": (color 255 64 64)
					"r": (color 255 75 75)
					default: (color 255 210 210)
				)
			)
			setPixels image [0, y - 1] pixels
		)
		image
	)

	fn fn_bs_make_root_mask =
	(
		local rows = #(
			"11111111100111111111",
			"11111111000011111111",
			"11111110000001111111",
			"11111100000000111111",
			"11111000000000011111",
			"11110000000000001111",
			"11100000000000000111",
			"11000000000000000011",
			"10000000000000000001",
			"00000000000000000000",
			"00000000000000000000",
			"10000000000000000001",
			"11000000000000000011",
			"11100000000000000111",
			"11110000000000001111",
			"11111000000000011111",
			"11111100000000111111",
			"11111110000001111111",
			"11111111000011111111",
			"11111111100111111111"
		)
		local image = bitmap 20 20 color:white

		for y = 1 to rows.count do
		(
			local pixels = for x = 1 to rows[y].count collect
			(
				if (substring rows[y] x 1) == "0" then black else white
			)
			setPixels image [0, y - 1] pixels
		)
		image
	)

	local bs_img_spine = bitmap 60 10 color:(color 15 176 199)
	local bs_img_blue = bitmap 38 40 color:(color 109 109 255)
	local bs_img_green = bitmap 36 40 color:(color 14 223 14)
	local bs_img_head = bitmap 40 28 color:(color 222 255 255)
	local bs_img_neck = bitmap 67 24 color:(color 15 176 199)
	local bs_img_pelvis = bitmap 60 20 color:(color 251 246 167)
	local bs_img_root = fn_bs_make_root_bitmap()
	local bs_img_root_mask = fn_bs_make_root_mask()

	-- Max 2026 can fail to paint procedurally-created Bitmap values when they
	-- are used directly by rollout image buttons.  Save the generated UI
	-- swatches as raw temporary BMP files and let the control load the files.
	fn fn_bs_save_ui_bitmap image file_name =
	(
		local file_path = (getDir #temp) + "\\" + file_name
		image.filename = file_path
		if (maxVersion())[1] >= 28000 then
			save image quiet:true outputColorConversion:#noConversion
		else
			save image quiet:true gamma:1.0
		file_path
	)

	local bs_img_spine_path = fn_bs_save_ui_bitmap bs_img_spine "Bipedsel_spine.bmp"
	local bs_img_blue_path = fn_bs_save_ui_bitmap bs_img_blue "Bipedsel_blue.bmp"
	local bs_img_green_path = fn_bs_save_ui_bitmap bs_img_green "Bipedsel_green.bmp"
	local bs_img_head_path = fn_bs_save_ui_bitmap bs_img_head "Bipedsel_head.bmp"
	local bs_img_neck_path = fn_bs_save_ui_bitmap bs_img_neck "Bipedsel_neck.bmp"
	local bs_img_pelvis_path = fn_bs_save_ui_bitmap bs_img_pelvis "Bipedsel_pelvis.bmp"
	local bs_img_root_path = fn_bs_save_ui_bitmap bs_img_root "Bipedsel_root.bmp"
	local bs_img_root_mask_path = fn_bs_save_ui_bitmap bs_img_root_mask "Bipedsel_root_mask.bmp"

	-- -------------------------------------------------------------------------
	-- Embedded color image and user-provided icon mask.
	-- The mask is black in transparent areas and white over the icons.
	-- Both PNG files are expanded to the 3ds Max temp directory.
	-- -------------------------------------------------------------------------
	fn fn_bs_write_base64_file file_path chunks =
	(
		local encoded = ""
		for chunk in chunks do encoded += chunk
		local bytes = (dotNetClass "System.Convert").FromBase64String encoded
		(dotNetClass "System.IO.File").WriteAllBytes file_path bytes
	)

	local bs_icon_png_data = #(\
		"iVBORw0KGgoAAAANSUhEUgAAAIAAAAAPCAYAAAAs2MfGAAAACXBIWXMAAAsTAAALEwEAmpwYAAAG7GlUWHRYTUw6Y29tLmFkb2Jl", \
		"LnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4gPHg6eG1wbWV0YSB4", \
		"bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgOS4xLWMwMDMgNzkuOTY5MGE4NywgMjAyNS8w", \
		"My8wNi0xOToxMjowMyAgICAgICAgIj4gPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJk", \
		"Zi1zeW50YXgtbnMjIj4gPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIgeG1sbnM6eG1wPSJodHRwOi8vbnMuYWRvYmUuY29t", \
		"L3hhcC8xLjAvIiB4bWxuczpkYz0iaHR0cDovL3B1cmwub3JnL2RjL2VsZW1lbnRzLzEuMS8iIHhtbG5zOnBob3Rvc2hvcD0iaHR0", \
		"cDovL25zLmFkb2JlLmNvbS9waG90b3Nob3AvMS4wLyIgeG1sbnM6eG1wTU09Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9t", \
		"bS8iIHhtbG5zOnN0RXZ0PSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvc1R5cGUvUmVzb3VyY2VFdmVudCMiIHhtcDpDcmVh", \
		"dG9yVG9vbD0iQWRvYmUgUGhvdG9zaG9wIDI2LjExIChXaW5kb3dzKSIgeG1wOkNyZWF0ZURhdGU9IjIwMjYtMDgtMjBUMTk6Mjc6", \
		"MTgrMDk6MDAiIHhtcDpNb2RpZnlEYXRlPSIyMDI2LTA4LTIwVDE5OjM2OjI1KzA5OjAwIiB4bXA6TWV0YWRhdGFEYXRlPSIyMDI2", \
		"LTA4LTIwVDE5OjM2OjI1KzA5OjAwIiBkYzpmb3JtYXQ9ImltYWdlL3BuZyIgcGhvdG9zaG9wOkNvbG9yTW9kZT0iMyIgeG1wTU06", \
		"SW5zdGFuY2VJRD0ieG1wLmlpZDoxYmIzZjg1MC0wM2JjLTZjNDItYmQxZC1kYmY3OGMzYWFlYjMiIHhtcE1NOkRvY3VtZW50SUQ9", \
		"ImFkb2JlOmRvY2lkOnBob3Rvc2hvcDplN2RkZWM1Zi01MjhhLWU3NDYtYjEzNy1kMDljNGZkODc1ZTgiIHhtcE1NOk9yaWdpbmFs", \
		"RG9jdW1lbnRJRD0ieG1wLmRpZDpmNzk4ZTQ3OS03MWJlLTA3NDQtYTk2Ny04YWQ3ODRjOGFkYjUiPiA8eG1wTU06SGlzdG9yeT4g", \
		"PHJkZjpTZXE+IDxyZGY6bGkgc3RFdnQ6YWN0aW9uPSJjcmVhdGVkIiBzdEV2dDppbnN0YW5jZUlEPSJ4bXAuaWlkOmY3OThlNDc5", \
		"LTcxYmUtMDc0NC1hOTY3LThhZDc4NGM4YWRiNSIgc3RFdnQ6d2hlbj0iMjAyNi0wOC0yMFQxOToyNzoxOCswOTowMCIgc3RFdnQ6", \
		"c29mdHdhcmVBZ2VudD0iQWRvYmUgUGhvdG9zaG9wIDI2LjExIChXaW5kb3dzKSIvPiA8cmRmOmxpIHN0RXZ0OmFjdGlvbj0iY29u", \
		"dmVydGVkIiBzdEV2dDpwYXJhbWV0ZXJzPSJmcm9tIGltYWdlL2JtcCB0byBpbWFnZS9wbmciLz4gPHJkZjpsaSBzdEV2dDphY3Rp", \
		"b249InNhdmVkIiBzdEV2dDppbnN0YW5jZUlEPSJ4bXAuaWlkOjg5NzgwNjg3LTQ3NzEtMWM0ZC1iYWE5LWVlNjg1ZGJiOWIyYyIg", \
		"c3RFdnQ6d2hlbj0iMjAyNi0wOC0yMFQxOTozMDowMSswOTowMCIgc3RFdnQ6c29mdHdhcmVBZ2VudD0iQWRvYmUgUGhvdG9zaG9w", \
		"IDI2LjExIChXaW5kb3dzKSIgc3RFdnQ6Y2hhbmdlZD0iLyIvPiA8cmRmOmxpIHN0RXZ0OmFjdGlvbj0ic2F2ZWQiIHN0RXZ0Omlu", \
		"c3RhbmNlSUQ9InhtcC5paWQ6MWJiM2Y4NTAtMDNiYy02YzQyLWJkMWQtZGJmNzhjM2FhZWIzIiBzdEV2dDp3aGVuPSIyMDI2LTA4", \
		"LTIwVDE5OjM2OjI1KzA5OjAwIiBzdEV2dDpzb2Z0d2FyZUFnZW50PSJBZG9iZSBQaG90b3Nob3AgMjYuMTEgKFdpbmRvd3MpIiBz", \
		"dEV2dDpjaGFuZ2VkPSIvIi8+IDwvcmRmOlNlcT4gPC94bXBNTTpIaXN0b3J5PiA8L3JkZjpEZXNjcmlwdGlvbj4gPC9yZGY6UkRG", \
		"PiA8L3g6eG1wbWV0YT4gPD94cGFja2V0IGVuZD0iciI/PpuJC9AAAARsSURBVFiF7VlLTBNRFD1v+olANEUK/tC4ERQ/NSEm/iKK", \
		"iSaNcSHExIWJCzVxUxO3LtS1CYtuXBgTozsjO2HhgliQmCgxCEYUjYq2IFCgaFqkH565M51hpu20005bP/EkE+a93ju8zj333Pte", \
		"GeccMq55vcuDJG54PAw50N3dnTY3EwGPx4DpqRB2bHHkfEYx4Ha7Dduq1+zOw+9fgzV14pzHo9zf9XoLemiEg78efg//2CcQwaYm", \
		"N/LWg026JPgRB19pBcv2vHhcOxdPAKtX6Pv8R4EEKAZ+LgJfP38EYwwB/xgsVhuApqw+X4PgG53pAaXg//gO9Pl6xbEgWNDQuB21", \
		"dQ70DLzJSqy/GWFBENW4ihSac/bbCcAY49zgQigzW44e5x/ev4NgseJMW2tWP/qOVgvwZRp8U62WBJT5FPz2k4c088Ew+OxsEP9q", \
		"8KvopbS1gbfsBGtv53j4sCQksFZcr1DqPgtcws0LVzQGT1qW+4J8SEDZbLc18iP7Gg3ZCwJgs6Yrwfw8EIul6D8Au91YBpUji4oJ", \
		"P2O8mklLpeBj937w5LsvxXcQFcB+zo7o3SjsJ06nW3Q8h8vlQW/vZbGeGyEByXYiAdhXSJkqWIzVayIBLUhNAvp7pq01zTb5jrJn", \
		"EKHALAqblOBiSDjzDUvB9w0jzBiqUOISEH30IIPJZs0oFwlCUfBEHIguSgEdGRmFs6YOi04HX1dtnASZygEhvAS+tAREwpmVQZ1B", \
		"hWZR2KQEm/WfI18KeGcnWGenNEdkQokJoKcAqdAjAQV/8OUoDu9tYEFSgTgQnPomjifmwOkySoJM5YCC/30e6O/rFYOfq7coJIv8", \
		"JiXYrH895+wxY7yJczHo6nn8CQqgRwKSff9YSAy2XKMXVAlKgaezgZ6nuTt3Ug0iDnX8LwB+6sQB0Z7KyrP+/rSGUC+DCGayiJmU", \
		"4EL9jyVJQPerBAF7E4ny7AKMKgCBtngul0sZz8wAw0MvsWOLVK9jyUOgrdt2KTaRCDA5+S3jllAuFTVOhxh8vSCrD65KhTmTElwM", \
		"CScSoAwQCUANYDYFePXKqwRdHYTBwUFlkepmjdRgIiCdAKqzXq+hi0aBiYBfVA+SfTVp1AiFyFZaqxEJJeQro/UmJbjcEm4WwsL1", \
		"BUYXDWxX74BvuIXI7Q62Z3Qzzld0iEY+n3QcTHLf3NyskMDhcGRMR9q7vx0ZEu9tNiDXfn0iMKfUcyLJug0OEGlS7agpNFL3KXve", \
		"AJAvvyDkFYBjKv98fYvhX04YPgiSa/3AwACjwIdCIczTJj0DSP7lDp2ObPUyWsbOhmrNC2ICULdmfZodKUtwGthUl7mR1Pwm0dWl", \
		"2Mzq/F4hgz7zz4jlehn3upTbofvdms/qa9L/f9H9s+DiWXfRCCUU4lRZWamUg1TI8i9nKu3/KaNJ2o0+X/ZJVQHqM/r7egpZ8n8Y", \
		"IYDcC8iQa38qxsfHqf0Xr9TgR2PAEm3UVaAdAR315kMC8nHWrtXMJXuIP1ZO8RfiF/rImsKtHo8/AAAAAElFTkSuQmCC"
	)
	local bs_icon_mask_data = #(\
		"iVBORw0KGgoAAAANSUhEUgAAAIAAAAAPCAIAAACjulCRAAAACXBIWXMAAAsTAAALEwEAmpwYAAAG7GlUWHRYTUw6Y29tLmFkb2Jl", \
		"LnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4gPHg6eG1wbWV0YSB4", \
		"bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgOS4xLWMwMDMgNzkuOTY5MGE4NywgMjAyNS8w", \
		"My8wNi0xOToxMjowMyAgICAgICAgIj4gPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJk", \
		"Zi1zeW50YXgtbnMjIj4gPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIgeG1sbnM6eG1wPSJodHRwOi8vbnMuYWRvYmUuY29t", \
		"L3hhcC8xLjAvIiB4bWxuczpkYz0iaHR0cDovL3B1cmwub3JnL2RjL2VsZW1lbnRzLzEuMS8iIHhtbG5zOnBob3Rvc2hvcD0iaHR0", \
		"cDovL25zLmFkb2JlLmNvbS9waG90b3Nob3AvMS4wLyIgeG1sbnM6eG1wTU09Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9t", \
		"bS8iIHhtbG5zOnN0RXZ0PSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvc1R5cGUvUmVzb3VyY2VFdmVudCMiIHhtcDpDcmVh", \
		"dG9yVG9vbD0iQWRvYmUgUGhvdG9zaG9wIDI2LjExIChXaW5kb3dzKSIgeG1wOkNyZWF0ZURhdGU9IjIwMjYtMDgtMjBUMTk6Mjc6", \
		"MTgrMDk6MDAiIHhtcDpNb2RpZnlEYXRlPSIyMDI2LTA4LTIwVDE5OjM5OjQ5KzA5OjAwIiB4bXA6TWV0YWRhdGFEYXRlPSIyMDI2", \
		"LTA4LTIwVDE5OjM5OjQ5KzA5OjAwIiBkYzpmb3JtYXQ9ImltYWdlL3BuZyIgcGhvdG9zaG9wOkNvbG9yTW9kZT0iMyIgeG1wTU06", \
		"SW5zdGFuY2VJRD0ieG1wLmlpZDpmNWE3MjY0ZS1kODY4LWFhNDEtYjAzZC04YmUzNTI2NjBiNGMiIHhtcE1NOkRvY3VtZW50SUQ9", \
		"ImFkb2JlOmRvY2lkOnBob3Rvc2hvcDoxMjVlOGQyNC01MWY4LTVmNGQtODFkZC1iN2U0MmFjZWNkMDkiIHhtcE1NOk9yaWdpbmFs", \
		"RG9jdW1lbnRJRD0ieG1wLmRpZDpmNzk4ZTQ3OS03MWJlLTA3NDQtYTk2Ny04YWQ3ODRjOGFkYjUiPiA8eG1wTU06SGlzdG9yeT4g", \
		"PHJkZjpTZXE+IDxyZGY6bGkgc3RFdnQ6YWN0aW9uPSJjcmVhdGVkIiBzdEV2dDppbnN0YW5jZUlEPSJ4bXAuaWlkOmY3OThlNDc5", \
		"LTcxYmUtMDc0NC1hOTY3LThhZDc4NGM4YWRiNSIgc3RFdnQ6d2hlbj0iMjAyNi0wOC0yMFQxOToyNzoxOCswOTowMCIgc3RFdnQ6", \
		"c29mdHdhcmVBZ2VudD0iQWRvYmUgUGhvdG9zaG9wIDI2LjExIChXaW5kb3dzKSIvPiA8cmRmOmxpIHN0RXZ0OmFjdGlvbj0iY29u", \
		"dmVydGVkIiBzdEV2dDpwYXJhbWV0ZXJzPSJmcm9tIGltYWdlL2JtcCB0byBpbWFnZS9wbmciLz4gPHJkZjpsaSBzdEV2dDphY3Rp", \
		"b249InNhdmVkIiBzdEV2dDppbnN0YW5jZUlEPSJ4bXAuaWlkOjg5NzgwNjg3LTQ3NzEtMWM0ZC1iYWE5LWVlNjg1ZGJiOWIyYyIg", \
		"c3RFdnQ6d2hlbj0iMjAyNi0wOC0yMFQxOTozMDowMSswOTowMCIgc3RFdnQ6c29mdHdhcmVBZ2VudD0iQWRvYmUgUGhvdG9zaG9w", \
		"IDI2LjExIChXaW5kb3dzKSIgc3RFdnQ6Y2hhbmdlZD0iLyIvPiA8cmRmOmxpIHN0RXZ0OmFjdGlvbj0ic2F2ZWQiIHN0RXZ0Omlu", \
		"c3RhbmNlSUQ9InhtcC5paWQ6ZjVhNzI2NGUtZDg2OC1hYTQxLWIwM2QtOGJlMzUyNjYwYjRjIiBzdEV2dDp3aGVuPSIyMDI2LTA4", \
		"LTIwVDE5OjM5OjQ5KzA5OjAwIiBzdEV2dDpzb2Z0d2FyZUFnZW50PSJBZG9iZSBQaG90b3Nob3AgMjYuMTEgKFdpbmRvd3MpIiBz", \
		"dEV2dDpjaGFuZ2VkPSIvIi8+IDwvcmRmOlNlcT4gPC94bXBNTTpIaXN0b3J5PiA8L3JkZjpEZXNjcmlwdGlvbj4gPC9yZGY6UkRG", \
		"PiA8L3g6eG1wbWV0YT4gPD94cGFja2V0IGVuZD0iciI/PopOsaMAAAEtSURBVFiF7VjbEoQgCIVm//+X2YedGBJFELOa9jw5FJcA", \
		"DxrCDiLiNQAgIvjAin6VPxgfyEGWjYiqNTDkcMQLS7itcaNzrSXQEN4NtGNFAbpuZM/a/Vs1hQLwBBQ7Pm8QPVa62WmRDD/Vpn5C", \
		"FFpaYqhfglYPnT4DjPxyTK30tUw546bjN9uVLlSiLi6prncGOCnbs5+qWuQeCbaLKEVMp5QTh7BuxuoMyHw25now2hDR93V4+U0T", \
		"OwV1CWesBrBPY7g9/IeORfeAATwi0cvi38Z8c8PKrcDraogDcWPQTpQizqCUKLYiX3qtT4oDkKZC5IPHR90ERSliOqVMpiBOXOaE", \
		"4LmgYaSvW0YMYWFkyvvRIOf/ipC5c45f/5R+CbxD2L6gFvJQO+DDZ3ISX8jR2D80pEoiAAAAAElFTkSuQmCC"
	)

	local bs_icon_png_path = (getDir #temp) + "\\Bipedsel_006_16.png"
	local bs_icon_mask_path = (getDir #temp) + "\\Bipedsel_006_16_icon_mask.png"
	fn_bs_write_base64_file bs_icon_png_path bs_icon_png_data
	fn_bs_write_base64_file bs_icon_mask_path bs_icon_mask_data
	bs_icon_png_data = undefined
	bs_icon_mask_data = undefined

	-- 3ds Max 2026 added doDisplayTransform as item 10 of an image-button
	-- specification.  These are UI/data colors, so keep them out of the scene
	-- display transform.  Older Max versions receive the legacy 8-item form.
	fn fn_bs_image_spec image mask image_count image_index invert_mask =
	(
		if (maxVersion())[1] >= 28000 then
			#(image, mask, image_count, image_index, image_index, image_index, image_index, invert_mask, false, false)
		else
			#(image, mask, image_count, image_index, image_index, image_index, image_index, invert_mask)
	)

	fn fn_bs_icon_img icon_index =
	(
		fn_bs_image_spec bs_icon_png_path bs_icon_mask_path 8 icon_index true
	)

	fn fn_bs_img str1 =
	(
		local image = case (toLower str1) of
		(
			"bipsel_spine.bmp": bs_img_spine_path
			"bipsel_blue.bmp": bs_img_blue_path
			"bipsel_green.bmp": bs_img_green_path
			"bipsel_head.bmp": bs_img_head_path
			"bipsel_neck.bmp": bs_img_neck_path
			"bipsel_pelvis.bmp": bs_img_pelvis_path
			default: undefined
		)
		fn_bs_image_spec image undefined 1 1 false
	)
	
	bipedsel_float = NewRolloutFloater "Bipedsel" 150 510
	
	rollout bs_biped_rol "biped"
	(
		button add_all_bip_btn "+ALL" pos:[2,4] width:29 height:18 tooltip:"Add all biped from scene"
		button hide_bip_btn "Hide" pos:[33,4] width:29 height:18 toolTip:"Hide all bodyparts of your Biped"
		button visible_bip_btn "Unhi" pos:[64,4] width:29 height:18 toolTip:"Visible all bodyparts of your Biped"
		dropdownList bs_lbx "" pos:[3,24] width:129 items:#()
		
		checkbutton figure_mode "" pos:[95,4] width:18 height:18 images:(fn_bs_icon_img 2) toolTip:"Figure Mode"
		
		button get_btn "" pos:[115,4] width:18 height:18 images:(fn_bs_icon_img 3) toolTip:"Get Biped from selection"
		
		button select_head_btn "Head" pos:[46,49] width:40 height:30 images:(fn_bs_img "bipsel_head.bmp") toolTip:"Head"
		
		button select_neck2_btn "-" pos:[54,80] width:24 height:15 images:(fn_bs_img "bipsel_neck.bmp") toolTip:"Neck 2"
		button select_neck1_btn "-" pos:[54,96] width:24 height:15 images:(fn_bs_img "bipsel_neck.bmp") toolTip:"Neck 1"
		
		button spine3_btn "-" pos:[38,112] width:56 height:18 images:(fn_bs_img "bipsel_spine.bmp")
		button spine2_btn "-" pos:[38,131] width:56 height:18 images:(fn_bs_img "bipsel_spine.bmp")
		button spine1_btn "-" pos:[38,150] width:56 height:18 images:(fn_bs_img "bipsel_spine.bmp")
		
		button select_root_btn "Root" pos:[46,170] width:40 height:22 images:(fn_bs_image_spec bs_img_root_path bs_img_root_mask_path 1 1 false) toolTip:"Root"
		
		button pelvis_btn "Pelvis" pos:[41,194] width:50 height:16 images:(fn_bs_img "bipsel_pelvis.bmp") toolTip:"Pelvis"
		
		button select_rclav_btn "R" pos:[21,90] width:28 height:19 images:(fn_bs_img "bipsel_green.bmp")
		button select_lclav_btn "L" pos:[83,90] width:28 height:19 images:(fn_bs_img "bipsel_blue.bmp")
		
		button select_ruparm_btn "R" pos:[4,110] width:21 height:28 images:(fn_bs_img "bipsel_green.bmp")
		button select_luparm_btn "L" pos:[107,110] width:21 height:28 images:(fn_bs_img "bipsel_blue.bmp")
		
		button select_rforarm_btn "R" pos:[4,139] width:21 height:28 images:(fn_bs_img "bipsel_green.bmp")
		button select_lforarm_btn "L" pos:[107,139] width:21 height:28 images:(fn_bs_img "bipsel_blue.bmp")
		
		button select_rhand_btn "R" pos:[1,168] width:23 height:22 images:(fn_bs_img "bipsel_green.bmp")
		button select_lhand_btn "L" pos:[108,168] width:23 height:22 images:(fn_bs_img "bipsel_blue.bmp")
		
		button select_rfinger1_btn "R" pos:[24,172] width:19 height:15 images:(fn_bs_img "bipsel_green.bmp") toolTip:"1st"
		button select_rfinger2_btn "R" pos:[18,191] width:13 height:23 images:(fn_bs_img "bipsel_green.bmp")  toolTip:"2nd"
		button select_rfinger3_btn "R" pos:[0,191] width:18 height:20 images:(fn_bs_img "bipsel_green.bmp")  toolTip:"other"
		
		button select_lfinger1_btn "L" pos:[89,172] width:19 height:15 images:(fn_bs_img "bipsel_blue.bmp") toolTip:"1st"
		button select_lfinger2_btn "L" pos:[102,191] width:13 height:23 images:(fn_bs_img "bipsel_blue.bmp") toolTip:"2nd"
		button select_lfinger3_btn "L" pos:[115,191] width:18 height:20 images:(fn_bs_img "bipsel_blue.bmp") toolTip:"other"
		
		button rtight_btn "R" pos:[40,211] width:22 height:33 images:(fn_bs_img "bipsel_green.bmp")
		button ltight_btn "L" pos:[70,211] width:22 height:33 images:(fn_bs_img "bipsel_blue.bmp")
		
		button rcalf_btn "R" pos:[40,245] width:22 height:33 images:(fn_bs_img "bipsel_green.bmp")
		button lcalf_btn "L" pos:[70,245] width:22 height:33 images:(fn_bs_img "bipsel_blue.bmp")
		
		button hose_right_btn "HR" pos:[20,256] width:19 height:18 toolTip:"Hose Right"
		button hose_left_btn "HL" pos:[94,256] width:19 height:18 toolTip:"Hose Left"
		
		button rfoot_btn "R" pos:[28,279] width:34 height:18 images:(fn_bs_img "bipsel_green.bmp")
		button lfoot_btn "L" pos:[70,279] width:34 height:18 images:(fn_bs_img "bipsel_blue.bmp")
		
		button rtoe_btn "R" pos:[8,280] width:19 height:17 images:(fn_bs_img "bipsel_green.bmp")
		button ltoe_btn "L" pos:[106,280] width:19 height:17 images:(fn_bs_img "bipsel_blue.bmp")
		
		button rponytail2_btn " " pos:[1,50] width:16 height:17 toolTip:"Ponytail 2 other"
		button rponytail1_btn "PT 2" pos:[18,50] width:26 height:17 toolTip:"Ponytail 2 1st"
		button lponytail1_btn "PT 1" pos:[88,50] width:26 height:17 toolTip:"Ponytail 1 1st"
		button lponytail2_btn " " pos:[115,50] width:16 height:17 toolTip:"Ponytail 1 other"
		
		button tail1_btn "T" pos:[94,216] width:15 height:12 images:(fn_bs_img "bipsel_pelvis.bmp") 
		button tail2_btn "T" pos:[94,229] width:15 height:12 images:(fn_bs_img "bipsel_pelvis.bmp")
		button tail3_btn "T" pos:[97,242] width:15 height:12 images:(fn_bs_img "bipsel_pelvis.bmp") 
		
		button all_btn "ALL" pos:[2,305] width:25 height:18 toolTip:"All bodyparts"
		button all2_btn "ALL2" pos:[29,305] width:29 height:18 toolTip:"All Bodyparts (deselect Footstep)"
		
		button select_root_v_btn "H" pos:[60,305] width:16 height:18 toolTip:"trackSelection Horizontal"
		button select_root_h_btn "V" pos:[78,305] width:16 height:18 toolTip:"trackSelection Vertical"
		button select_root_r_btn "T" pos:[96,305] width:16 height:18 toolTip:"trackSelection Turn"
		button make_key "" pos:[114,305] width:18 height:18 images:(fn_bs_icon_img 4) toolTip:"Create Biped Key"
		
		button fingerR1_btn "1" pos:[2,349] width:20 height:18 toolTip:"right 1st finger joints"
		button fingerR2_btn "2" pos:[24,349] width:20 height:18 toolTip:"right 2nd finger joints"
		button fingerR3_btn "FR" pos:[46,349] width:20 height:18 toolTip:"right 3rd finger joints"
		button fingerL3_btn "FL" pos:[68,349] width:20 height:18 toolTip:"left 3rd finger joints"
		button fingerL2_btn "2" pos:[90,349] width:20 height:18 toolTip:"left 2nd finger joints"
		button fingerL1_btn "1" pos:[112,349] width:20 height:18 toolTip:"left 1st finger joints"
		
		button prop1_btn "P1" pos:[2,327] width:20 height:18 
		button prop2_btn "P2" pos:[24,327] width:20 height:18
		button prop3_btn "P3" pos:[46,327] width:20 height:18
		
		button setPlantedKey_btn "" pos:[68,327] width:20 height:18 images:(fn_bs_icon_img 5) toolTip:"Set Planted Key"
		
		button setSlidingKey_btn "" pos:[90,327] width:20 height:18 images:(fn_bs_icon_img 6) toolTip:"Set Sliding Key"
		
		button setFreeKey_btn "" pos:[112,327] width:20 height:18 images:(fn_bs_icon_img 7) toolTip:"Set Free Key"
		
		button select_rarm_btn " " pos:[1,80] width:18 height:18 toolTip:"Right Arm"
		button select_larm_btn " " pos:[114,80] width:18 height:18 toolTip:"Left Arm"
		
		button select_rfinger_all_btn " " pos:[1,218] width:18 height:18 toolTip:"Right All Fingers"
		button select_lfinger_all_btn " " pos:[114,218] width:18 height:18 toolTip:"Left All Fingers"
		
		button select_rfoot_btn " " pos:[1,258] width:18 height:18 toolTip:"Right Foot"
		button select_lfoot_btn " " pos:[114,258] width:18 height:18 toolTip:"Left Foot"
		
		on make_key pressed do
		(
			for o in selection do
			(
				if classof o == Biped_Object then
				(
					c = o.controller
					if classof c == Vertical_Horizontal_Turn then
					(
						biped.addNewKey c[1] slidertime
						biped.addNewKey c[2] slidertime
						biped.addNewKey c[3] slidertime
					)
					else biped.addNewKey c slidertime
				)
			)
		)
		
		on setPlantedKey_btn pressed do
		(
			for o in selection where classof o == Biped_Object and classof o.controller != Vertical_Horizontal_Turn do 
			(
				c = bs_biped.transform.controller
				if state != c.figuremode do biped.setPlantedKey o
			)
		)
		
		on setSlidingKey_btn pressed do
		(
			for o in selection where classof o == Biped_Object and classof o.controller != Vertical_Horizontal_Turn do 
			(
				c = bs_biped.transform.controller
				if state != c.figuremode do biped.setSlidingKey o
			)
		)
		
		on setFreeKey_btn pressed do
		(
			for o in selection where classof o == Biped_Object and classof o.controller != Vertical_Horizontal_Turn do 
			(
				c = bs_biped.transform.controller
				if state != c.figuremode do biped.setFreeKey o
			)
		)
		
		on figure_mode changed state do
		(
			try 
			(
				c = bs_biped.transform.controller
				if state != c.figuremode then
				(
					biped.setCurrentLayer c 0
					c.figuremode = state
					if state == false then biped.setCurrentLayer c (biped.numLayers c)
				)
			) catch ()
		)
		
		on hide_bip_btn pressed do
		(
			disableSceneRedraw()
			
			for k in bs_lbx.items do 
			(
				obj = getNodeByName k
				
				if obj != undefined and classof obj.controller == Vertical_Horizontal_Turn do 
				(
					for i=1 to 25 do (for j=1 to 25 do try ( hide (biped.getNode obj i link:j ) ) catch())
				)
			)
			
			enableSceneRedraw()
			reDrawViews()
		)
		
		on visible_bip_btn pressed do
		(
			disableSceneRedraw()
			
			for k in bs_lbx.items do 
			(
				obj = getNodeByName k
				
				if obj != undefined and classof obj.controller == Vertical_Horizontal_Turn do 
				(
					for i=1 to 25 do (for j=1 to 25 do try ( unhide (biped.getNode obj i link:j ) ) catch())
				)
			)
			
			enableSceneRedraw()
			reDrawViews()
		)
		
		fn fn_bs_lbx_selected i =
		(
--				i = bs_lbx.selection
			if i > 0 and bs_lbx.items.count > 0 do
			(
				obj = getNodeByName bs_lbx.items[i]
				
				if obj != undefined and classof obj.controller == Vertical_Horizontal_Turn do 
				(
					bs_biped = obj
					local bip = bs_biped.controller
					if (bip.leglinks == 3 and hose_left_btn.visible) or (bip.leglinks != 3 and not hose_left_btn.visible) do \
						hose_left_btn.visible = hose_right_btn.visible = hose_left_btn.enabled = hose_right_btn.enabled = not hose_left_btn.visible
				)
			)
		)
		
		on bs_lbx selected i do fn_bs_lbx_selected i
		
		on add_all_bip_btn pressed do
		(
			local bs_names = for o in Geometry where classOf o == Biped_Object and classof o.controller == Vertical_Horizontal_Turn collect o.name
			sort bs_names
			bs_lbx.items = bs_names
			if bs_names.count > 0 then
			(
				bs_lbx.selection = 1
				fn_bs_lbx_selected 1
				bs_biped = getNodeByName bs_lbx.items[1]
			)
		)
		
		on bs_biped_rol open do add_all_bip_btn.pressed()
		
		on get_btn pressed do
		(
			if $ != undefined and classof selection[1] == Biped_Object do
			(
				a = biped.getNode selection[1] 13
				local i = findItem bs_biped_rol.bs_lbx.items a.name
				if i != 0 do 
				(
					bs_biped = a
					bs_biped_rol.bs_lbx.selection = i
				)
			)
		)
		
		on select_head_btn pressed do ( fn_sel_obj 11 1 )
		on select_neck1_btn pressed do ( fn_sel_obj 17 1 )
		on spine2_btn pressed do ( fn_sel_obj 9 2 )
		on spine1_btn pressed do ( fn_sel_obj 9 1 )
		on pelvis_btn pressed do ( fn_sel_obj 12 1 )
		on select_root_btn pressed do ( fn_sel_obj 13 1 )
		on select_rclav_btn pressed do ( fn_sel_obj 2 1 )
		on select_lclav_btn pressed do ( fn_sel_obj 1 1 )
		on select_ruparm_btn pressed do ( fn_sel_obj 2 2 )
		on select_luparm_btn pressed do ( fn_sel_obj 1 2 )
		on select_rforarm_btn pressed do ( fn_sel_obj 2 3 )
		on select_lforarm_btn pressed do ( fn_sel_obj 1 3 )
		on select_rhand_btn pressed do ( fn_sel_obj 2 4 )
		on select_lhand_btn pressed do ( fn_sel_obj 1 4 )
		on rtight_btn pressed do ( fn_sel_obj 6 1 )
		on ltight_btn pressed do ( fn_sel_obj 5 1 )
		on rcalf_btn pressed do ( fn_sel_obj 6 2 )
		on lcalf_btn pressed do ( fn_sel_obj 5 2 )
		on hose_right_btn pressed do ( fn_sel_obj 6 3 )
		on hose_left_btn pressed do ( fn_sel_obj 5 3 )
		on tail1_btn pressed do ( fn_sel_obj 10 1 )
		on tail2_btn pressed do ( fn_sel_obj 10 2 )
		on prop1_btn pressed do ( fn_sel_obj 20 1 )
		on prop2_btn pressed do ( fn_sel_obj 21 1 )
		on prop3_btn pressed do ( fn_sel_obj 22 1 )
		
		on lponytail1_btn pressed do ( fn_sel_obj 18 1 )
		on rponytail1_btn pressed do ( fn_sel_obj 19 1 )
		
		on lponytail2_btn pressed do if fn_bs_ensure_biped() do (fn_sel_obj2 18 2 (bs_biped.controller.ponytail1Links))
		on rponytail2_btn pressed do if fn_bs_ensure_biped() do (fn_sel_obj2 19 2 (bs_biped.controller.ponytail2Links))
		
		on select_larm_btn pressed do (fn_sel_obj2 1 1 4)
		on select_rarm_btn pressed do (fn_sel_obj2 2 1 4)
		
		on tail3_btn pressed do if fn_bs_ensure_biped() do (fn_sel_obj2 10 3 (bs_biped.controller.tailLinks))
		on select_neck2_btn pressed do if fn_bs_ensure_biped() do (fn_sel_obj2 17 2 (bs_biped.controller.neckLinks))
		on spine3_btn pressed do if fn_bs_ensure_biped() do (fn_sel_obj2 9 3 (bs_biped.controller.spineLinks))
		on select_lfoot_btn pressed do if fn_bs_ensure_biped() do (fn_sel_obj2 5 1 (bs_biped.controller.leglinks))
		on select_rfoot_btn pressed do if fn_bs_ensure_biped() do (fn_sel_obj2 6 1 (bs_biped.controller.leglinks))
		on rfoot_btn pressed do if fn_bs_ensure_biped() do (fn_sel_obj 6 (bs_biped.controller.leglinks))
		on lfoot_btn pressed do if fn_bs_ensure_biped() do (fn_sel_obj 5 (bs_biped.controller.leglinks))
		
		on ltoe_btn pressed do
		(
			if fn_bs_ensure_biped() do
			(
				local bip = bs_biped.controller
				fn_sel_obj2 7 1 (bip.toes * bip.toeLinks)
			)
		)
		
		on rtoe_btn pressed do
		(
			if fn_bs_ensure_biped() do
			(
				local bip = bs_biped.controller
				fn_sel_obj2 8 1 (bip.toes * bip.toeLinks)
			)
		)
		
		on select_rfinger1_btn pressed do
		(if fn_bs_ensure_biped() do fn_sel_obj2 4 1 (bs_biped.controller.fingerlinks))
		
		on select_rfinger2_btn pressed do
		(
			if fn_bs_ensure_biped() do
			(
				lk = bs_biped.controller.fingerlinks
				fn_sel_obj2 4 (lk+1) (lk*2)
			)
		)
		
		on select_rfinger3_btn pressed do
		(
			if fn_bs_ensure_biped() do
			(
				lk = bs_biped.controller.fingerlinks
				fn_sel_obj2 4 (lk*2+1) (bs_biped.controller.fingers * lk)
			)
		)
		
		on select_lfinger1_btn pressed do if fn_bs_ensure_biped() do (fn_sel_obj2 3 1 (bs_biped.controller.fingerlinks))
		
		
		on select_lfinger2_btn pressed do
		(
			if fn_bs_ensure_biped() do
			(
				lk = bs_biped.controller.fingerlinks
				fn_sel_obj2 3 (lk+1) (lk*2)
			)
		)
		
		on select_lfinger3_btn pressed do
		(
			if fn_bs_ensure_biped() do
			(
				lk = bs_biped.controller.fingerlinks
				fn_sel_obj2 3 (lk*2+1) (bs_biped.controller.fingers * lk)
			)
		)
		
		fn fn_sel_finger a b =
		(
			disableSceneRedraw()
			try
			(
				c = bs_biped.controller.fingerlinks
				sl = biped.getNode bs_biped a link:(b+c)
				fn_sel_obj a (b+c)
				local selArr = for i = 2 to 4 collect (biped.getNode bs_biped a link:(i*c+b))
				if sl.isSelected then (selectMore selArr) else (deselect selArr)
			) catch()
			enableSceneRedraw()
			reDrawViews()
		)
		
		on fingerL1_btn pressed do fn_sel_finger 3 3 
		on fingerL2_btn pressed do fn_sel_finger 3 2 
		on fingerL3_btn pressed do fn_sel_finger 3 1 
		on fingerR1_btn pressed do fn_sel_finger 4 3 
		on fingerR2_btn pressed do fn_sel_finger 4 2 
		on fingerR3_btn pressed do fn_sel_finger 4 1 
		
		on all_btn pressed do
		(
			disableSceneRedraw()
			clearNodeSelection()
			s = #()
			for i=1 to 24 do 
			(
				for j=1 to 25 do 
				(
					try
					(
						a = biped.getNode bs_biped i link:j 
						if a != undefined then ( append s a )
					) catch()
				)
			)
			selectMore s
			enableSceneRedraw()
			reDrawViews()
		)
		
		on all2_btn pressed do
		(
			all_btn.pressed()
			try ( deselect (biped.getNode bs_biped 16 ) ) catch()
		)
		
		on select_lfinger_all_btn pressed do 
		(
			if fn_bs_ensure_biped() do
			(
				local bip = bs_biped.controller
				fn_sel_obj2 3 1 (bip.fingers * bip.fingerLinks)
			)
		)	
		
		on select_rfinger_all_btn pressed do 
		(
			if fn_bs_ensure_biped() do
			(
				local bip = bs_biped.controller
				fn_sel_obj2 4 1 (bip.fingers * bip.fingerLinks)
			)
		)
		
		on select_root_v_btn pressed do if fn_bs_ensure_biped() do bs_biped.transform.controller.trackSelection = 1
		on select_root_h_btn pressed do if fn_bs_ensure_biped() do bs_biped.transform.controller.trackSelection = 2
		on select_root_r_btn pressed do if fn_bs_ensure_biped() do bs_biped.transform.controller.trackSelection = 3
	)

	addRollout bs_biped_rol bipedsel_float rolledUp:false


	rollout bs_commands_roll "Commands"
	(
		button hide_select_btn "Hide select" pos:[2,4] width:62 height:18
		button unhide_select_btn "Unhi select" pos:[68,4] width:62 height:18
		
		button copy_key "copy" pos:[2,26] width:40 height:18 
		button paste_keye "paste" pos:[46,26] width:40 height:18 
		button paster_keye "pasteR" pos:[90,26] width:40 height:18 
		
		label l_ease_to "Ease To :" pos:[6,51]
		button ease_to_0 "0" pos:[69,51] width:29 height:15 toolTip:"Ease To : 0"
		button ease_to_50 "50" pos:[101,51] width:29 height:15 toolTip:"Ease To : 50"
		
		label l_ease_from "Ease From :" pos:[6,70]
		button ease_from_0 "0" pos:[69,70] width:29 height:15 toolTip:"Ease From : 0"
		button ease_from_50 "50" pos:[101,70] width:29 height:15 toolTip:"Ease From : 50"
			
		label l_tension "Tension :" pos:[6,89]
		button tension_25 "25" pos:[69,89] width:29 height:15 toolTip:"Ease To : 0"
		button tension_50 "50" pos:[101,89] width:29 height:15 toolTip:"Ease To : 50"
		
		label l_continuity "Continuity :" pos:[6,108]
		button continuity_0 "0" pos:[69,108] width:29 height:15 toolTip:"Ease To : 0"
		button continuity_25 "25" pos:[101,108] width:29 height:15 toolTip:"Ease To : 50"
		
		on copy_key pressed do 
		(
			try -- pose delete
			(
				if bs_pose_str != undefined then biped.deleteCopy selection[1].controller #posture bs_pose_str
			) catch()
			
			try -- pose copy
			(
				bs_pose_str = biped.copyPosture selection[1].controller #posture false false true
			) catch()
		)
		
		on paste_keye pressed do 
		(
			try -- pose paste
			(
				biped.pastePosture selection[1].controller #posture false bs_pose_str
			) catch()
		)
		
		on paster_keye pressed do 
		(
			try -- pose paste
			(
				biped.pastePosture selection[1].controller #posture true bs_pose_str
			) catch()
		)
		on hide_select_btn pressed do
		(
			disableSceneRedraw()
			for i=1 to 24 do (
				for j=1 to 25 do (
					try ( hide (biped.getNode bs_biped i link:j ) ) catch()
				)
			)
			try ( hide bs_biped ) catch()
			enableSceneRedraw()
			reDrawViews()
		)
		
		on unhide_select_btn pressed do
		(
			disableSceneRedraw()
			for i=1 to 24 do (
				for j=1 to 25 do (
					try ( unhide (biped.getNode bs_biped i link:j ) ) catch()
				)
			)
			try ( unhide bs_biped ) catch()
			enableSceneRedraw()
			reDrawViews()
		)
		
		fn getrootkeyindex ctr tm =
		(
			i = 0
			do (
				i += 1
				cause = 0
				bool1 = true
				if ctr.keys == undefined or ctr.keys[i] == undefined then
				(
					cause = 1
					bool1 = false
				)
				else if ctr.keys[i].time == tm then
				(
					cause = 2
					bool1 = false
				)
			)
			while bool1 
			
			if cause == 1 do i = 0
			i
		)
		
		fn key_info p1 p2 =
		(
			c1 = 0
			c2 = 0
			for o in selection where classof o == Biped_Object do
			(
				cnt = o.controller
				if classof cnt != Vertical_Horizontal_Turn then cnt = #(cnt)
				for c in cnt do
				(
					idx = getrootkeyindex c slidertime
					if idx == 0 then c1 += 1
					else
					(
						c2 += 1
						k = biped.getkey c idx
						case p1 of
						(
							1:	k.easeTo = p2
							2:	k.easeFrom = p2
							3:	k.tension = p2
							4:	k.continuity = p2
						)
					)
				)
			)
			if c1 > 0 then messagebox(c2 as string + " object(s) status is changed\n" \
											+ "but " + c1 as string + " object(s) don't have key.")
		)
		
		on ease_to_0 pressed do ( key_info 1 0 )
		on ease_to_50 pressed do ( key_info 1 50 )
		on ease_from_0 pressed do ( key_info 2 0 )
		on ease_from_50 pressed do ( key_info 2 50 )
		on tension_25 pressed do ( key_info 3 25 )
		on tension_50 pressed do ( key_info 3 50 )
		on continuity_0 pressed do ( key_info 4 0 )
		on continuity_25 pressed do ( key_info 4 25 )
		
	)

	addRollout bs_commands_roll bipedsel_float rolledUp:true

	rollout bs_fingers_roll "Fingers"
	(
		label label_rfinger "Right" pos:[100,5] 
		
		button select_rfinger1_1_btn "1" pos:[2,5] width:20 height:17 images:(fn_bs_img "bipsel_green.bmp")
		button select_rfinger1_2_btn "2" pos:[22,5] width:25 height:17 images:(fn_bs_img "bipsel_green.bmp")
		button select_rfinger1_3_btn "3" pos:[47,5] width:25 height:17 images:(fn_bs_img "bipsel_green.bmp")
		button select_rfinger1_4_btn "4" pos:[72,5] width:25 height:17 images:(fn_bs_img "bipsel_green.bmp")
		
		button select_rfinger2_1_btn "1" pos:[2,26] width:20 height:16 images:(fn_bs_img "bipsel_green.bmp")
		button select_rfinger2_2_btn "2" pos:[22,26] width:35 height:16 images:(fn_bs_img "bipsel_green.bmp")
		button select_rfinger2_3_btn "3" pos:[57,26] width:35 height:16 images:(fn_bs_img "bipsel_green.bmp")
		button select_rfinger2_4_btn "4" pos:[92,26] width:35 height:16 images:(fn_bs_img "bipsel_green.bmp")
		
		button select_rfinger3_1_btn "1" pos:[2,45] width:20 height:16 images:(fn_bs_img "bipsel_green.bmp")
		button select_rfinger3_2_btn "2" pos:[22,45] width:36 height:16 images:(fn_bs_img "bipsel_green.bmp")
		button select_rfinger3_3_btn "3" pos:[58,45] width:36 height:16 images:(fn_bs_img "bipsel_green.bmp")
		button select_rfinger3_4_btn "4" pos:[94,45] width:36 height:16 images:(fn_bs_img "bipsel_green.bmp")
		
		button select_rfinger4_1_btn "1" pos:[2,64] width:20 height:16 images:(fn_bs_img "bipsel_green.bmp")
		button select_rfinger4_2_btn "2" pos:[22,64] width:34 height:16 images:(fn_bs_img "bipsel_green.bmp")
		button select_rfinger4_3_btn "3" pos:[56,64] width:34 height:16 images:(fn_bs_img "bipsel_green.bmp")
		button select_rfinger4_4_btn "4" pos:[90,64] width:34 height:16 images:(fn_bs_img "bipsel_green.bmp")
		
		button select_rfinger5_1_btn "1" pos:[2,83] width:20 height:16 images:(fn_bs_img "bipsel_green.bmp")
		button select_rfinger5_2_btn "2" pos:[22,83] width:30 height:16 images:(fn_bs_img "bipsel_green.bmp")
		button select_rfinger5_3_btn "3" pos:[52,83] width:30 height:16 images:(fn_bs_img "bipsel_green.bmp")
		button select_rfinger5_4_btn "4" pos:[82,83] width:30 height:16 images:(fn_bs_img "bipsel_green.bmp")
		
		button select_rfingerA_1_btn "" pos:[2,102] width:20 height:16
		button select_rfingerA_2_btn "" pos:[27,102] width:20 height:16
		button select_rfingerA_3_btn "" pos:[57,102] width:20 height:16
		button select_rfingerA_4_btn "" pos:[87,102] width:20 height:16
		
		label label_lfinger "Left" pos:[100,124] 
		
		button select_lfinger1_1_btn "1" pos:[2,124] width:20 height:17 images:(fn_bs_img "bipsel_blue.bmp")
		button select_lfinger1_2_btn "2" pos:[22,124] width:25 height:17 images:(fn_bs_img "bipsel_blue.bmp")
		button select_lfinger1_3_btn "3" pos:[47,124] width:25 height:17 images:(fn_bs_img "bipsel_blue.bmp")
		button select_lfinger1_4_btn "4" pos:[72,124] width:25 height:17 images:(fn_bs_img "bipsel_blue.bmp")
		
		button select_lfinger2_1_btn "1" pos:[2,145] width:20 height:16 images:(fn_bs_img "bipsel_blue.bmp")
		button select_lfinger2_2_btn "2" pos:[22,145] width:35 height:16 images:(fn_bs_img "bipsel_blue.bmp")
		button select_lfinger2_3_btn "3" pos:[57,145] width:35 height:16 images:(fn_bs_img "bipsel_blue.bmp")
		button select_lfinger2_4_btn "4" pos:[92,145] width:35 height:16 images:(fn_bs_img "bipsel_blue.bmp")
		
		button select_lfinger3_1_btn "1" pos:[2,164] width:20 height:16 images:(fn_bs_img "bipsel_blue.bmp")
		button select_lfinger3_2_btn "2" pos:[22,164] width:36 height:16 images:(fn_bs_img "bipsel_blue.bmp")
		button select_lfinger3_3_btn "3" pos:[58,164] width:36 height:16 images:(fn_bs_img "bipsel_blue.bmp")
		button select_lfinger3_4_btn "4" pos:[94,164] width:36 height:16 images:(fn_bs_img "bipsel_blue.bmp")
		
		button select_lfinger4_1_btn "1" pos:[2,183] width:20 height:16 images:(fn_bs_img "bipsel_blue.bmp")
		button select_lfinger4_2_btn "2" pos:[22,183] width:34 height:16 images:(fn_bs_img "bipsel_blue.bmp")
		button select_lfinger4_3_btn "3" pos:[56,183] width:34 height:16 images:(fn_bs_img "bipsel_blue.bmp")
		button select_lfinger4_4_btn "4" pos:[90,183] width:34 height:16 images:(fn_bs_img "bipsel_blue.bmp")
		
		button select_lfinger5_1_btn "1" pos:[2,202] width:20 height:16 images:(fn_bs_img "bipsel_blue.bmp")
		button select_lfinger5_2_btn "2" pos:[22,202] width:30 height:16 images:(fn_bs_img "bipsel_blue.bmp")
		button select_lfinger5_3_btn "3" pos:[52,202] width:30 height:16 images:(fn_bs_img "bipsel_blue.bmp")
		button select_lfinger5_4_btn "4" pos:[82,202] width:30 height:16 images:(fn_bs_img "bipsel_blue.bmp")
		
		button select_lfingerA_1_btn "" pos:[2,221] width:20 height:16
		button select_lfingerA_2_btn "" pos:[27,221] width:20 height:16
		button select_lfingerA_3_btn "" pos:[57,221] width:20 height:16
		button select_lfingerA_4_btn "" pos:[87,221] width:20 height:16
		
		fn fn_sel_finger a b c =
		(
			try(
				local bip = bs_biped.controller
				local d = bip.fingerLinks + c - 4
				if bip.fingers >= b and 0 < d and d <= bip.fingerLinks do fn_sel_obj a (bip.fingerLinks*(b-1) + d)
			) catch()
		)
		
		fn fn_sel_finger5 a c =
		(
			try(
				local bip = bs_biped.controller
				local d = bip.fingerLinks + c - 4
				if 0 < d and d <= bip.fingerLinks do 
				(
					bs = (for b = 1 to bip.fingers collect (bip.fingerLinks*(b-1) + d))
					fn_sel_obj3 a bs
				)
			) catch()
		)
		
		on select_rfinger1_1_btn pressed do ( fn_sel_finger 4 1 1 )
		on select_rfinger1_2_btn pressed do ( fn_sel_finger 4 1 2 )
		on select_rfinger1_3_btn pressed do ( fn_sel_finger 4 1 3 )
		on select_rfinger1_4_btn pressed do ( fn_sel_finger 4 1 4 )
		on select_rfinger2_1_btn pressed do ( fn_sel_finger 4 2 1 )
		on select_rfinger2_2_btn pressed do ( fn_sel_finger 4 2 2 )
		on select_rfinger2_3_btn pressed do ( fn_sel_finger 4 2 3 )
		on select_rfinger2_4_btn pressed do ( fn_sel_finger 4 2 4 )
		on select_rfinger3_1_btn pressed do ( fn_sel_finger 4 3 1 )
		on select_rfinger3_2_btn pressed do ( fn_sel_finger 4 3 2 )
		on select_rfinger3_3_btn pressed do ( fn_sel_finger 4 3 3 )
		on select_rfinger3_4_btn pressed do ( fn_sel_finger 4 3 4 )
		on select_rfinger4_1_btn pressed do ( fn_sel_finger 4 4 1 )
		on select_rfinger4_2_btn pressed do ( fn_sel_finger 4 4 2 )
		on select_rfinger4_3_btn pressed do ( fn_sel_finger 4 4 3 )
		on select_rfinger4_4_btn pressed do ( fn_sel_finger 4 4 4 )
		on select_rfinger5_1_btn pressed do ( fn_sel_finger 4 5 1 )
		on select_rfinger5_2_btn pressed do ( fn_sel_finger 4 5 2 )
		on select_rfinger5_3_btn pressed do ( fn_sel_finger 4 5 3 )
		on select_rfinger5_4_btn pressed do ( fn_sel_finger 4 5 4 )
		
		on select_lfinger1_1_btn pressed do ( fn_sel_finger 3 1 1 )
		on select_lfinger1_2_btn pressed do ( fn_sel_finger 3 1 2 )
		on select_lfinger1_3_btn pressed do ( fn_sel_finger 3 1 3 )
		on select_lfinger1_4_btn pressed do ( fn_sel_finger 3 1 4 )
		on select_lfinger2_1_btn pressed do ( fn_sel_finger 3 2 1 )
		on select_lfinger2_2_btn pressed do ( fn_sel_finger 3 2 2 )
		on select_lfinger2_3_btn pressed do ( fn_sel_finger 3 2 3 )
		on select_lfinger2_4_btn pressed do ( fn_sel_finger 3 2 4 )
		on select_lfinger3_1_btn pressed do ( fn_sel_finger 3 3 1 )
		on select_lfinger3_2_btn pressed do ( fn_sel_finger 3 3 2 )
		on select_lfinger3_3_btn pressed do ( fn_sel_finger 3 3 3 )
		on select_lfinger3_4_btn pressed do ( fn_sel_finger 3 3 4 )
		on select_lfinger4_1_btn pressed do ( fn_sel_finger 3 4 1 )
		on select_lfinger4_2_btn pressed do ( fn_sel_finger 3 4 2 )
		on select_lfinger4_3_btn pressed do ( fn_sel_finger 3 4 3 )
		on select_lfinger4_4_btn pressed do ( fn_sel_finger 3 4 4 )
		on select_lfinger5_1_btn pressed do ( fn_sel_finger 3 5 1 )
		on select_lfinger5_2_btn pressed do ( fn_sel_finger 3 5 2 )
		on select_lfinger5_3_btn pressed do ( fn_sel_finger 3 5 3 )
		on select_lfinger5_4_btn pressed do ( fn_sel_finger 3 5 4 )
		
		on select_rfingerA_1_btn pressed do ( fn_sel_finger5 4 1 )
		on select_rfingerA_2_btn pressed do ( fn_sel_finger5 4 2 )
		on select_rfingerA_3_btn pressed do ( fn_sel_finger5 4 3 )
		on select_rfingerA_4_btn pressed do ( fn_sel_finger5 4 4 )
		
		on select_lfingerA_1_btn pressed do ( fn_sel_finger5 3 1 )
		on select_lfingerA_2_btn pressed do ( fn_sel_finger5 3 2 )
		on select_lfingerA_3_btn pressed do ( fn_sel_finger5 3 3 )
		on select_lfingerA_4_btn pressed do ( fn_sel_finger5 3 4 )
	)
	addRollout bs_fingers_roll bipedsel_float rolledUp:true


	rollout bs_toes_roll "Toes"
	(
		label label_rtoe "R Toe" pos:[85,5] 
		
		button select_rtoe1_1_btn "1" pos:[2,5] width:25 height:18 images:(fn_bs_img "bipsel_green.bmp")
		button select_rtoe1_2_btn "2" pos:[27,5] width:25 height:18 images:(fn_bs_img "bipsel_green.bmp")
		button select_rtoe1_3_btn "3" pos:[52,5] width:25 height:18 images:(fn_bs_img "bipsel_green.bmp")
		
		button select_rtoe2_1_btn "1" pos:[9,27] width:39 height:15 images:(fn_bs_img "bipsel_green.bmp")
		button select_rtoe2_2_btn "2" pos:[48,27] width:39 height:15 images:(fn_bs_img "bipsel_green.bmp")
		button select_rtoe2_3_btn "3" pos:[87,27] width:39 height:15 images:(fn_bs_img "bipsel_green.bmp")
		
		button select_rtoe3_1_btn "1" pos:[9,45] width:40 height:15 images:(fn_bs_img "bipsel_green.bmp")
		button select_rtoe3_2_btn "2" pos:[49,45] width:40 height:15 images:(fn_bs_img "bipsel_green.bmp")
		button select_rtoe3_3_btn "3" pos:[89,45] width:40 height:15 images:(fn_bs_img "bipsel_green.bmp")
		
		button select_rtoe4_1_btn "1" pos:[9,63] width:38 height:15 images:(fn_bs_img "bipsel_green.bmp")
		button select_rtoe4_2_btn "2" pos:[47,63] width:38 height:15 images:(fn_bs_img "bipsel_green.bmp")
		button select_rtoe4_3_btn "3" pos:[85,63] width:38 height:15 images:(fn_bs_img "bipsel_green.bmp")
		
		button select_rtoe5_1_btn "1" pos:[9,81] width:34 height:15 images:(fn_bs_img "bipsel_green.bmp")
		button select_rtoe5_2_btn "2" pos:[43,81] width:34 height:15 images:(fn_bs_img "bipsel_green.bmp")
		button select_rtoe5_3_btn "3" pos:[77,81] width:34 height:15 images:(fn_bs_img "bipsel_green.bmp")
		
		label label_ltoe "L Toe" pos:[85,105] 
		
		button select_ltoe1_1_btn "1" pos:[2,105] width:25 height:18 images:(fn_bs_img "bipsel_blue.bmp")
		button select_ltoe1_2_btn "2" pos:[27,105] width:25 height:18 images:(fn_bs_img "bipsel_blue.bmp")
		button select_ltoe1_3_btn "3" pos:[52,105] width:25 height:18 images:(fn_bs_img "bipsel_blue.bmp")
		
		button select_ltoe2_1_btn "1" pos:[9,127] width:39 height:15 images:(fn_bs_img "bipsel_blue.bmp")
		button select_ltoe2_2_btn "2" pos:[48,127] width:39 height:15 images:(fn_bs_img "bipsel_blue.bmp")
		button select_ltoe2_3_btn "3" pos:[87,127] width:39 height:15 images:(fn_bs_img "bipsel_blue.bmp")
		
		button select_ltoe3_1_btn "1" pos:[9,145] width:40 height:15 images:(fn_bs_img "bipsel_blue.bmp")
		button select_ltoe3_2_btn "2" pos:[49,145] width:40 height:15 images:(fn_bs_img "bipsel_blue.bmp")
		button select_ltoe3_3_btn "3" pos:[89,145] width:40 height:15 images:(fn_bs_img "bipsel_blue.bmp")
		
		button select_ltoe4_1_btn "1" pos:[9,163] width:38 height:15 images:(fn_bs_img "bipsel_blue.bmp")
		button select_ltoe4_2_btn "2" pos:[47,163] width:38 height:15 images:(fn_bs_img "bipsel_blue.bmp")
		button select_ltoe4_3_btn "3" pos:[85,163] width:38 height:15 images:(fn_bs_img "bipsel_blue.bmp")
		
		button select_ltoe5_1_btn "1" pos:[9,181] width:34 height:15 images:(fn_bs_img "bipsel_blue.bmp")
		button select_ltoe5_2_btn "2" pos:[43,181] width:34 height:15 images:(fn_bs_img "bipsel_blue.bmp")
		button select_ltoe5_3_btn "3" pos:[77,181] width:34 height:15 images:(fn_bs_img "bipsel_blue.bmp")
		
		
		
		on select_rtoe_all_btn pressed do (
			try(
				local bip = bs_biped.controller
				fn_sel_obj2 8 1 (bip.toes * bip.toeLinks)
			) catch()
		)
		
		on select_ltoe_all_btn pressed do (
			try(
				local bip = bs_biped.controller
				fn_sel_obj2 7 1 (bip.toes * bip.toeLinks)
			) catch()
		)
		
		fn fn_sel_toe a b c =
		(
			try(
				local bip = bs_biped.controller
				if bip.toes >= b and bip.toeLinks >= c then fn_sel_obj a (bip.fingerLinks*(b-1) + c)
			) catch()
		)
		
		on select_rtoe1_1_btn pressed do ( fn_sel_toe 8 1 1 )
		on select_rtoe1_2_btn pressed do ( fn_sel_toe 8 1 2 )
		on select_rtoe1_3_btn pressed do ( fn_sel_toe 8 1 3 )
		on select_rtoe2_1_btn pressed do ( fn_sel_toe 8 2 1 )
		on select_rtoe2_2_btn pressed do ( fn_sel_toe 8 2 2 )
		on select_rtoe2_3_btn pressed do ( fn_sel_toe 8 2 3 )
		on select_rtoe3_1_btn pressed do ( fn_sel_toe 8 3 1 )
		on select_rtoe3_2_btn pressed do ( fn_sel_toe 8 3 2 )
		on select_rtoe3_3_btn pressed do ( fn_sel_toe 8 3 3 )
		on select_rtoe4_1_btn pressed do ( fn_sel_toe 8 4 1 )
		on select_rtoe4_2_btn pressed do ( fn_sel_toe 8 4 2 )
		on select_rtoe4_3_btn pressed do ( fn_sel_toe 8 4 3 )
		on select_rtoe5_1_btn pressed do ( fn_sel_toe 8 5 1 )
		on select_rtoe5_2_btn pressed do ( fn_sel_toe 8 5 2 )
		on select_rtoe5_3_btn pressed do ( fn_sel_toe 8 5 3 )
		on select_ltoe1_1_btn pressed do ( fn_sel_toe 7 1 1 )
		on select_ltoe1_2_btn pressed do ( fn_sel_toe 7 1 2 )
		on select_ltoe1_3_btn pressed do ( fn_sel_toe 7 1 3 )
		on select_ltoe2_1_btn pressed do ( fn_sel_toe 7 2 1 )
		on select_ltoe2_2_btn pressed do ( fn_sel_toe 7 2 2 )
		on select_ltoe2_3_btn pressed do ( fn_sel_toe 7 2 3 )
		on select_ltoe3_1_btn pressed do ( fn_sel_toe 7 3 1 )
		on select_ltoe3_2_btn pressed do ( fn_sel_toe 7 3 2 )
		on select_ltoe3_3_btn pressed do ( fn_sel_toe 7 3 3 )
		on select_ltoe4_1_btn pressed do ( fn_sel_toe 7 4 1 )
		on select_ltoe4_2_btn pressed do ( fn_sel_toe 7 4 2 )
		on select_ltoe4_3_btn pressed do ( fn_sel_toe 7 4 3 )
		on select_ltoe5_1_btn pressed do ( fn_sel_toe 7 5 1 )
		on select_ltoe5_2_btn pressed do ( fn_sel_toe 7 5 2 )
		on select_ltoe5_3_btn pressed do ( fn_sel_toe 7 5 3 )
	)
	addRollout bs_toes_roll bipedsel_float rolledUp:true


	rollout bs_other_roll "Other"
	(
		button select_ptail1_all_btn "Pony1" pos:[2,5] width:40 height:15 tooltip:"All ponytail 1 objects"
		button select_ptail2_all_btn "Pony2" pos:[2,25] width:40 height:15 tooltip:"All ponytail 2 objects"

		button select_ptail1_1_btn "1" pos:[45,5] width:15 height:15
		button select_ptail1_2_btn "2" pos:[63,5] width:15 height:15
		button select_ptail1_3_btn "3" pos:[81,5] width:15 height:15
		button select_ptail1_4_btn "4" pos:[99,5] width:15 height:15
		button select_ptail1_5_btn "5" pos:[117,5] width:15 height:15

		button select_ptail2_1_btn "1" pos:[45,25] width:15 height:15
		button select_ptail2_2_btn "2" pos:[63,25] width:15 height:15
		button select_ptail2_3_btn "3" pos:[81,25] width:15 height:15
		button select_ptail2_4_btn "4" pos:[99,25] width:15 height:15
		button select_ptail2_5_btn "5" pos:[117,25] width:15 height:15
		
		on select_ptail1_all_btn pressed do if fn_bs_ensure_biped() do (fn_sel_obj2 18 1 (bs_biped.controller.ponytail1Links))
		on select_ptail2_all_btn pressed do if fn_bs_ensure_biped() do (fn_sel_obj2 19 1 (bs_biped.controller.ponytail2Links))

		on select_ptail1_1_btn pressed do ( fn_sel_obj 18 1 )
		on select_ptail1_2_btn pressed do ( fn_sel_obj 18 2 )
		on select_ptail1_3_btn pressed do ( fn_sel_obj 18 3 )
		on select_ptail1_4_btn pressed do ( fn_sel_obj 18 4 )
		on select_ptail1_5_btn pressed do ( fn_sel_obj 18 5 )
		
		on select_ptail2_1_btn pressed do ( fn_sel_obj 19 1 )
		on select_ptail2_2_btn pressed do ( fn_sel_obj 19 2 )
		on select_ptail2_3_btn pressed do ( fn_sel_obj 19 3 )
		on select_ptail2_4_btn pressed do ( fn_sel_obj 19 4 )
		on select_ptail2_5_btn pressed do ( fn_sel_obj 19 5 )

		button select_neck_all_btn "Neck" pos:[2,45] width:40 height:15 tooltip:"All neck objects"
		button select_neck1_btn "1" pos:[45,45] width:15 height:15
		button select_neck2_btn "2" pos:[63,45] width:15 height:15
		button select_neck3_btn "3" pos:[81,45] width:15 height:15
		button select_neck4_btn "4" pos:[99,45] width:15 height:15
		button select_neck5_btn "5" pos:[117,45] width:15 height:15
		
		on select_neck_all_btn pressed do if fn_bs_ensure_biped() do (fn_sel_obj2 17 1 (bs_biped.controller.neckLinks))
		on select_neck1_btn pressed do ( fn_sel_obj 17 1 )
		on select_neck2_btn pressed do ( fn_sel_obj 17 2 )
		on select_neck3_btn pressed do ( fn_sel_obj 17 3 )
		on select_neck4_btn pressed do ( fn_sel_obj 17 4 )
		on select_neck5_btn pressed do ( fn_sel_obj 17 5 )
		
		button select_spine_all_btn "Spine" pos:[2,65] width:40 height:15 tooltip:"All spine objects"
		button select_spine1_btn "1" pos:[45,65] width:15 height:15
		button select_spine2_btn "2" pos:[63,65] width:15 height:15
		button select_spine3_btn "3" pos:[81,65] width:15 height:15
		button select_spine4_btn "4" pos:[99,65] width:15 height:15
		button select_spine5_btn "5" pos:[117,65] width:15 height:15
		
		on select_spine_all_btn pressed do if fn_bs_ensure_biped() do (fn_sel_obj2 9 1 (bs_biped.controller.spineLinks))
		on select_spine1_btn pressed do ( fn_sel_obj 9 1 )
		on select_spine2_btn pressed do ( fn_sel_obj 9 2 )
		on select_spine3_btn pressed do ( fn_sel_obj 9 3 )
		on select_spine4_btn pressed do ( fn_sel_obj 9 4 )
		on select_spine5_btn pressed do ( fn_sel_obj 9 5 )
		
		button select_tail_all_btn "Tail" pos:[2,85] width:40 height:15 tooltip:"All tail objects"
		button select_tail1_btn "1" pos:[45,85] width:15 height:15
		button select_tail2_btn "2" pos:[63,85] width:15 height:15
		button select_tail3_btn "3" pos:[81,85] width:15 height:15
		button select_tail4_btn "4" pos:[99,85] width:15 height:15
		button select_tail5_btn "5" pos:[117,85] width:15 height:15
		
		on select_tail_all_btn pressed do if fn_bs_ensure_biped() do (fn_sel_obj2 10 1 (bs_biped.controller.tailLinks))
		on select_tail1_btn pressed do ( fn_sel_obj 10 1 )
		on select_tail2_btn pressed do ( fn_sel_obj 10 2 )
		on select_tail3_btn pressed do ( fn_sel_obj 10 3 )
		on select_tail4_btn pressed do ( fn_sel_obj 10 4 )
		on select_tail5_btn pressed do ( fn_sel_obj 10 5 )
	)
	addRollout bs_other_roll bipedsel_float rolledUp:true
	
	rollout bs_about_roll "About"
	(
		label script2 "Bipedsel 1.20a"
		label author4 "DiGiMonkey"
		label blank2 "***"
		label script "Bipedsel 1.19"
		label author3 "(c)Harada Daisuke"
		label web3 "http://d00.cool.ne.jp/"
		label year "2002/12/27"
		label year2 "2010/05/23"
		label blank "***"
		label lab0 "Basic Script"
		label basicscript "Biped Selector 1.3"
		label author1 "Saku Partamies"
		label web1 "http://www.partamies.com"
		label lab1 "and"
		label author2 "Juha Takabe"
		label web2 "http://www.saunalahti.fi/jukota/"
	)
	addRollout bs_about_roll bipedsel_float rolledUp:true
) 
